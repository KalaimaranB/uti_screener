from ultralytics import YOLO


model = YOLO("yolov8s.pt")

#This function trains our model using the open source dataset for UTI strips 
#Image resolution was set to 640, to reduce training compute time, and epochs was set to 25
#This means that the training algorithm only does 25 passes of the data, and optimizes each pass 
#More passes = more fine tuned model, but due to computational limiations only 25 were used
results = model.train(
    data="urine_dataset/data.yaml", 
    epochs=300,                     
    imgsz= 1024,                     
    patience=50,                                    
    plots=True, 
    workers = 1, 
    batch = 8, 
    device="mps"             
)