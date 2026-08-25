import onnxruntime as ort

session = ort.InferenceSession("sprout.onnx")

print("--- Inputs ---")
for x in session.get_inputs():
    print(f"Name: {x.name}, Type: {x.type}")

print("\n--- Outputs ---")
for y in session.get_outputs():
    print(f"Name: {y.name}, Type: {y.type}")
