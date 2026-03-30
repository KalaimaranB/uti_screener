import cv2
from ultralytics import YOLO

def process_test_strip_simple(image_path, model_path):
    # 1. LOAD IMAGE & MODEL
    image = cv2.imread(image_path)
    if image is None:
        print("Error: Could not load image.")
        return

    model = YOLO(model_path)
    
    
    results = model.predict(image, conf=0.7)
    
    
    if len(results[0].boxes) == 0:
        print("YOLO could not find the strip in this image.")
        return

    # Loop through detected boxes to find the 'strip'
    for box in results[0].boxes:
        class_id = int(box.cls[0])
        class_name = model.names[class_id]

        if class_name == 'strip':
            # 3. GET EXACT YOLO CORNERS (x_min, y_min, x_max, y_max)
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # 4. CROP THE IMAGE TO THOSE CORNERS
            # OpenCV arrays are sliced as [y_start:y_end, x_start:x_end]
            cropped_strip = image[y1:y2, x1:x2]
            x_length  = x2 - x1 
            y_length = y2 - y1

            if x_length > y_length: 
                cropped_strip = cv2.rotate(cropped_strip,cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # 5. STANDARDIZE THE SIZE 
            
            standardized_strip = cv2.resize(cropped_strip, (100, 800))

            cv2.imwrite("cropped_result.jpg", standardized_strip)
            return

# --- EXECUTE ---
# REMEMBER: Update these paths to point to your specific files!
my_model = "runs/detect/train2/weights/best.pt" 
my_image = "tests/samples/UTI Sample3.png"

process_test_strip_simple(my_image, my_model)