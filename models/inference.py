import onnxruntime as ort

# Explicitly initialize the session using DirectML
providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
session = ort.InferenceSession("best.onnx", providers=providers)
