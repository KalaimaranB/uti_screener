import cv2
from ultralytics import YOLO

#This function completes the image preprocessing stage 
#of the analysis. It takes in a path to the image to be analyzed
#and the path to the model to be used. The model file contains the 
#parameters and weights of the model. 
def process_test_strip_simple(image_path, model_path):
    # 1. LOAD IMAGE & MODEL
    image = cv2.imread(image_path)
    if image is None:
        print("Error: Could not load image.")
        return
    # Loading in model trained with the open source dataset
    model = YOLO(model_path)

    print("\n--- Model Info ---")
    # This prints the summary including GFLOPs to the console
    # This is only used for the speed testing, and can be commented out
    model.info() 
    print("------------------\n")
    
    #Completed the object detection on the provided image. 
    results = model.predict(image, conf=0.7)
    
    #If no strip is detected, print an error message and return
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

            #This line rotates the UTI strip if it is detected to be
            #lying horizontally in the image. If the UTI strip is vertical
            #the code will not rotate it. This makes sure the strip is in
            #a consistent orientation for downstream analysis. 
            if x_length > y_length: 
                cropped_strip = cv2.rotate(cropped_strip,cv2.ROTATE_90_COUNTERCLOCKWISE)
            
            # 5. Resize the image to make downstream analysis simpler, 
            #    The image is resized to 100x800 pixels, with the width 
            # being 100 pixels and the height being 800 pixels to match the
            #size of the UTI test strip. 
            
            standardized_strip = cv2.resize(cropped_strip, (100, 800))
            #This line saves the standardized strip to a file, that will be loaded in downstream analysis. 
            cv2.imwrite("cropped_result.jpg", standardized_strip)
            return

# --- EXECUTE ---
# REMEMBER: Update these paths to point to your specific files!
my_model = "runs/detect/train2/weights/best.pt" 
my_image = "tests/samples/UTI Sample3.png"

process_test_strip_simple(my_image, my_model)