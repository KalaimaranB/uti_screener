import os
import cv2
import tempfile
from pathlib import Path
from ultralytics import YOLO

from core.calibration import CalibrationModel
from core.strip_analyzer import StripAnalyzer
from api.clinical_classifier import evaluate_diagnoses

class ImageAnalysisRunner:
    """
    Facade class to orchestrate the internal machine learning and clinical diagnostic pipeline.
    It encapsulates: 
      1. YOLO strip detection & cropping.
      2. Color sampling & calibration.
      3. Clinical rule evaluation.
    """
    def __init__(self, 
                 yolo_path="runs/detect/train2/weights/best.pt",
                 calib_model_path="models/model.json",
                 config_path="config/strip_config.json"):
        self.yolo_path = yolo_path
        self.calib_model_path = calib_model_path
        self.config_path = config_path

        # Lazy loading of models to prevent stalling the import level
        self.yolo_model = None
        self.calib_model = None
        self.analyzer = None

    def _initialize_models(self):
        """Loads models on the first analysis run."""
        if self.yolo_model is None:
            self.yolo_model = YOLO(self.yolo_path)
        if self.calib_model is None:
            self.calib_model = CalibrationModel.load(self.calib_model_path)
        if self.analyzer is None:
            self.analyzer = StripAnalyzer()

    def crop_strip_with_yolo(self, image_path: str) -> str | None:
        """
        Uses YOLO to detect the 'strip' and saves a cropped temporary image.
        Returns the path to the cropped image, or None if no strip is detected.
        """
        image = cv2.imread(image_path)
        if image is None:
            return None

        results = self.yolo_model.predict(image, conf=0.7)
        if len(results[0].boxes) == 0:
            return None

        # Loop through detected boxes to find the 'strip'
        for box in results[0].boxes:
            class_id = int(box.cls[0])
            class_name = self.yolo_model.names[class_id]

            if class_name == 'strip':
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cropped_strip = image[y1:y2, x1:x2]
                
                # Auto-rotate horizontal strips to vertical (sync with testModel.py changes)
                x_length = x2 - x1 
                y_length = y2 - y1
                if x_length > y_length: 
                    cropped_strip = cv2.rotate(cropped_strip, cv2.ROTATE_90_COUNTERCLOCKWISE)
                
                # Standardize the size according to testModel.py specification
                standardized_strip = cv2.resize(cropped_strip, (100, 800))
                
                # Create a temporary file to hold the cropped image
                fd, temp_path = tempfile.mkstemp(suffix=".jpg")
                os.close(fd)
                
                cv2.imwrite(temp_path, standardized_strip)
                return temp_path
                
        return None

    def analyze_uploaded_image(self, image_path: str, progress_callback=None) -> dict:
        """
        Orchestrates the complete image analysis pipeline.
        Returns a dictionary formatted for presentation in the UI.
        """
        if progress_callback: progress_callback("Loading application models from memory...")
        self._initialize_models()
        
        # 1. Detect and Crop Image
        if progress_callback: progress_callback("Running YOLO computer vision to isolate strip...")
        cropped_path = self.crop_strip_with_yolo(image_path)
        if not cropped_path:
            return {
                "status": "Failed to detect test strip",
                "summary": "The test strip could not be found in the image. Please ensure good lighting and clear visibility of the strip bounds.",
                "detected_class": "None",
                "confidence": "N/A",
                "diagnoses": [],
                "biomarkers": {},
                "debug_image_path": None
            }
            
        # 2. Analyze the Cropped strip
        # Save the debug annotated image for UI rendering
        debug_fd, debug_path = tempfile.mkstemp(suffix="_debug.png")
        os.close(debug_fd)
        
        if progress_callback: progress_callback("Segmenting reagent pads and sampling colors against clinical calibration maps...")
        
        try:
            # We enforce pre_cropped=True because we just did YOLO cropping and standardized it specifically.
            results_normal = self.analyzer.analyze_with_debug(
                image_path=cropped_path,
                model=self.calib_model,
                strip_config_path=self.config_path,
                debug_output_path=debug_path,
                pre_cropped=True
            )
            conf_norm = sum(b.confidence for b in results_normal.values()) / len(results_normal) if results_normal else 0.0
            
            # 2B. 180-Degree Inversion Check (Upside Down Strips)
            img_bgr = cv2.imread(cropped_path)
            img_flipped = cv2.rotate(img_bgr, cv2.ROTATE_180)
            
            flip_fd, flip_path = tempfile.mkstemp(suffix=".jpg")
            os.close(flip_fd)
            cv2.imwrite(flip_path, img_flipped)
            
            flip_dbg_fd, flip_dbg_path = tempfile.mkstemp(suffix="_debug.png")
            os.close(flip_dbg_fd)
            
            results_flipped = self.analyzer.analyze_with_debug(
                image_path=flip_path,
                model=self.calib_model,
                strip_config_path=self.config_path,
                debug_output_path=flip_dbg_path,
                pre_cropped=True
            )
            conf_flip = sum(b.confidence for b in results_flipped.values()) / len(results_flipped) if results_flipped else 0.0
            
            # Require the inverted layout to beat the normal layout by a visible margin (5%) to avoid noise swaps
            if conf_flip > conf_norm + 0.05:
                results = results_flipped
                final_debug_path = flip_dbg_path
                avg_conf = conf_flip
            else:
                results = results_normal
                final_debug_path = debug_path
                avg_conf = conf_norm
                
            try: os.remove(flip_path)
            except Exception: pass
        except Exception as e:
            if os.path.exists(cropped_path):
                os.remove(cropped_path)
            return {
                "status": "Analysis failed",
                "summary": f"Could not process the padded strip boxes: {str(e)}",
                "detected_class": "strip",
                "confidence": "N/A",
                "diagnoses": [],
                "biomarkers": {},
                "debug_image_path": None
            }
            
        # 3. Clinical evaluate heuristic rules
        if progress_callback: progress_callback("Applying clinical heuristic guidelines to classify pathologies...")
        diagnoses = evaluate_diagnoses(results)
        
        summary = "No significant pathogenic biomarker combinations detected."
        if diagnoses:
            summary = " \\n".join(diagnoses) # Joined with new line for readable presentation
            
        # Aggregate confidence is already selected by the optimal orientation matrix
        
        biomarkers = {
            k: {
                "value": v.value,
                "unit": v.unit,
                "confidence": v.confidence,
                "color_rgb": v.color_rgb
            }
            for k, v in results.items()
        }

        # Cleanup cropped temp file automatically leaving debug_path for UI
        if os.path.exists(cropped_path):
            os.remove(cropped_path)
            
        return {
            "status": "Analysis complete",
            "summary": summary,
            "detected_class": "strip",
            "confidence": f"{avg_conf:.1%}",
            "diagnoses": diagnoses,
            "biomarkers": biomarkers,
            "debug_image_path": final_debug_path
        }

# Instantiate a global instance to keep models loaded across Streamlit re-runs
_runner = ImageAnalysisRunner()

def analyze_uploaded_image(image_path: str, progress_callback=None) -> dict:
    """Public functional wrapper to analyze an image through the full pipeline."""
    return _runner.analyze_uploaded_image(image_path, progress_callback=progress_callback)
