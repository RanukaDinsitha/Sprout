from ultralytics import YOLO

# Load your local trained 76-class classification model
model = YOLO("models/best.pt")

# Export to web-optimized ONNX format
model.export(format="onnx")