import torch
import torch_directml

# =========================================================================
# STEP 1: PURE DIRECTML TENSOR MEMORY WRAPPER
# =========================================================================
dml_device = torch_directml.device()
print(f"\n[Sandbox Setup] Active AMD GPU Engine Initialized: {dml_device}")

# Keep PyTorch environment flags configured accurately for a CPU+DirectML build
# This completely eliminates the "Torch not compiled with CUDA enabled" crash
torch.cuda.is_available = lambda: False
torch.cuda.device_count = lambda: 0

# Intercept and redirect tensor math allocations directly onto your AMD hardware
_orig_to = torch.Tensor.to
def directml_tensor_redirect(self, *args, **kwargs):
    # Catch any instruction attempting to map weights to processing devices
    if args and isinstance(args[0], (str, torch.device)):
        # If Ultralytics requests a data step on cpu/cuda, pipe it straight to DirectML
        return _orig_to(self, dml_device, **{k: v for k, v in kwargs.items() if k != 'non_blocking'})
    return _orig_to(self, *args, **kwargs)

# Overwrite PyTorch's global allocation module in memory
torch.Tensor.to = directml_tensor_redirect

# Force the Ultralytics string device parser to look for a clean CPU baseline layout
# (This keeps the internal configuration stable while our tensor redirect handles the GPU)
import ultralytics.utils.torch_utils as torch_utils
torch_utils.select_device = lambda *args, **kwargs: torch.device('cpu')
# =========================================================================

from ultralytics import YOLO

def main():
    print("[Sprout] Initializing model layers...")
    model = YOLO("yolo26m-cls.pt")
    
    # Run the ultra-fast internal sandbox training sample
    results = model.train(
        data="mnist160",  # Tiny 1MB sample built right into Ultralytics
        epochs=2,
        imgsz=32,
        batch=2,
        device="cpu",     # Keep this set to 'cpu' so the framework initializes stably
        workers=0,        # Prevents Windows parallel execution memory freezes
        amp=False,        # DirectML performs best with standard FP32 execution blocks
        cache=False
    )

if __name__ == "__main__":
    main()
