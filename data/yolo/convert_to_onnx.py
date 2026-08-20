import torch
import torch.nn as nn
import torch.nn.functional as F
import sys
from contextlib import contextmanager

NUM_CLASSES = 77
MODEL_PATH = "sprout.pth"
OUTPUT_ONNX = "sprout.onnx"

@contextmanager
def force_cpu_tensor_rebuild():
    """Only active while loading sprout.pth — patches removed immediately after."""
    import torch._utils
    orig_numpy = torch._utils._rebuild_device_tensor_from_numpy

    def patched_numpy(data, dtype, device, requires_grad):
        return orig_numpy(data, dtype, torch.device("cpu"), requires_grad)

    torch._utils._rebuild_device_tensor_from_numpy = patched_numpy
    try:
        yield
    finally:
        torch._utils._rebuild_device_tensor_from_numpy = orig_numpy

class OptimizedArcFaceInference(nn.Module):
    def __init__(self, in_features, out_classes):
        super().__init__()
        self.weight = nn.Parameter(torch.FloatTensor(out_classes, in_features))

    def forward(self, features):
        return F.linear(F.normalize(features), F.normalize(self.weight))

class BioCLIPClassifierInference(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        try:
            import open_clip
        except ImportError:
            print("❌ open_clip missing. Run: pip install open-clip-torch")
            sys.exit(1)

        model, _, _ = open_clip.create_model_and_transforms('hf-hub:imageomics/bioclip')
        self.backbone = model.visual
        self.neck = nn.Sequential(
            nn.BatchNorm1d(512),
            nn.Linear(512, 512),
            nn.ReLU()
        )
        self.head = OptimizedArcFaceInference(in_features=512, out_classes=num_classes)

    def forward(self, x):
        feat = self.backbone(x)
        return self.head(self.neck(feat))

def main():
    print("📦 Rebuilding inference model architecture...")
    model = BioCLIPClassifierInference(NUM_CLASSES)   # open_clip loads its own weights, unpatched

    print(f"📂 Loading weights from {MODEL_PATH}...")
    try:
        state_dict = torch.load(MODEL_PATH, map_location="cpu", weights_only=True)
    except Exception:
        print("⚠️ weights_only load failed, retrying with device-rebuild patch...")
        with force_cpu_tensor_rebuild():
            state_dict = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)

    if isinstance(state_dict, dict) and "state_dict" in state_dict:
        state_dict = state_dict["state_dict"]
    elif isinstance(state_dict, dict) and "model" in state_dict:
        state_dict = state_dict["model"]

    if any(k.startswith("module.") for k in state_dict.keys()):
        state_dict = {k.replace("module.", "", 1): v for k, v in state_dict.items()}

    clean_state_dict = {
        k: v for k, v in state_dict.items()
        if not any(x in k for x in ["cos_m", "sin_m", "th", "mm"])
    }

    missing, unexpected = model.load_state_dict(clean_state_dict, strict=False)
    if missing:
        print(f"⚠️ Missing keys: {missing}")
    if unexpected:
        print(f"⚠️ Unexpected keys: {unexpected}")

    model.eval()
    dummy_input = torch.randn(1, 3, 224, 224, dtype=torch.float32)

    print(f"⚡ Tracing graph and exporting to {OUTPUT_ONNX}...")
    try:
        torch.onnx.export(
            model,
            (dummy_input,),
            OUTPUT_ONNX,
            export_params=True,
            opset_version=17,
            input_names=['input_image'],
            output_names=['logits'],
            dynamic_axes={'input_image': {0: 'batch_size'}, 'logits': {0: 'batch_size'}}
        )
        print("🎉 ONNX conversion successful!")
    except Exception as e:
        print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    main()