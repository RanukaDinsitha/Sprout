from ultralytics import YOLO
import os

def main():
    # 1. Load YOLO11 Nano Classification model
    model = YOLO("yolo26m-cls.pt") 

    # 2. Train Classification Model
    results = model.train(
        data=r"C:\Users\ranuk\Downloads\Sprout\data\yolo\images",  # Points directly to images directory containing train/ and val/
        epochs=100,            
        imgsz=224,             # Standard resolution for classification
        batch=16,              
        
        # Output paths
        project="model",  
        name="sprout_cls",       
        save=True,             
        device="cpu"           # Set to "cpu" for CPU execution
    )

    print("\nThe training of the model has been completed successfully.")
    print(f"Weights have been saved to: {os.path.abspath('model/sprout_cls/weights/best.pt')}")

if __name__ == "__main__":
    main()
