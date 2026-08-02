import os
import cv2
import numpy as np
from onnxruntime.quantization import quantize_static, QuantFormat, QuantType, CalibrationDataReader

# 1. Setup Data Reader tuned for YOLO26 Classification (224x224)
class Yolo26ClsCalibrationDataReader(CalibrationDataReader):
    def __init__(self, image_folder, target_size=(224, 224)):
        # Collect valid image formats
        self.image_paths = [os.path.join(image_folder, f) for f in os.listdir(image_folder) 
                            if f.lower().endswith(('.png', '.jpg', '.jpeg'))][:100]
        self.data_iter = iter(self.image_paths)
        self.target_size = target_size

    def preprocess(self, img_path):
        img = cv2.imread(img_path)
        if img is None:
            # Fallback tensor mapping the expected classification shape
            return np.zeros((1, 3, self.target_size[0], self.target_size[1]), dtype=np.float32)
        
        # YOLO26-cls uses standard square crop/resize configurations
        img = cv2.resize(img, self.target_size)
        img = img.astype(np.float32) / 255.0  # ImageNet standardization range scale
        img = np.transpose(img, (2, 0, 1))    # Rearrange HWC channels to CHW
        return np.expand_dims(img, axis=0)     # Shape out to batch dim: (1, 3, 224, 224)

    def get_next(self):
        next_path = next(self.data_iter, None)
        if next_path is not None:
            # Default input dictionary pointer for Ultralytics ONNX Classification
            return {"images": self.preprocess(next_path)}
        return {}  # Explicit dictionary closeout to satisfy Pylance signatures

# 2. Execute Quantization Pipeline
# Place 10-100 sample images representing your validation target labels inside your folder
data_reader = Yolo26ClsCalibrationDataReader(image_folder="data/yolo/images")

quantize_static(
    model_input=os.path.join("models", "best.onnx"),
    model_output=os.path.join("models", "best-quant.onnx"),
    calibration_data_reader=data_reader,
    quant_format=QuantFormat.QDQ,          # Standard universally accepted structure
    activation_type=QuantType.QUInt8,      # Unsigned 8-bit mapping for cross-platform CPU execution
    weight_type=QuantType.QInt8            # Signed 8-bit tracking for static weights
)

print("YOLO26m-cls standard INT8 static quantization completed!")
