from flask import Flask, render_template, request, jsonify
import tensorflow as tf
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import img_to_array
from PIL import Image
from os.path import join
import numpy as np
import io

app = Flask(__name__)

# CONFIGURATION: Change these to match your model's parameters
MODEL_PATH = join("model", "ai.keras")
IMAGE_SIZE = 224 # Target width/height your model expects

# Safe global model loading on server startup
try:
    model = load_model(MODEL_PATH)
    print("✓ Keras AI Engine successfully loaded into memory.")
    
    # AUTOMATIC DETECTOR: 
    # This reads the exact number of classes directly from your model file
    NUM_CLASSES = model.output_shape[-1]
    print(f"✓ Dynamic Setup: Detected exactly {NUM_CLASSES} classes.")
    
    # Creates a generic list dynamically: ["Class 0", "Class 1", ... up to your exact total]
    CLASS_LABELS = [f"Class {i}" for i in range(NUM_CLASSES)]
    
except Exception as e:
    print(f"⚠️ Critical Error loading model: {e}")
    model = None
    CLASS_LABELS = []
    
@app.route('/')
def home():
    # Renders your exact HTML UI
    return render_template('index.html')

@app.route('/predict', methods=['POST'])
def predict():
    if model is None:
        return jsonify({"error": "AI Model file is missing or misconfigured on the server."}), 500

    if 'file' not in request.files:
        return jsonify({"error": "No image payload found in request."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No file selected."}), 400

    try:
        # 1. Read the image stream natively
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        
        # 2. Resize to match your network geometry
        resized_image = image.resize((IMAGE_SIZE, IMAGE_SIZE)) 
        img_array = img_to_array(resized_image)
        img_array = np.expand_dims(img_array, axis=0)
        
        # 3. Scale pixel values (0-1 normalization)
        img_array = img_array / 255.0  

        # 4. Run inference
        predictions = model.predict(img_array)[0]
        top_idx = np.argmax(predictions)
        
        return jsonify({
            "class": CLASS_LABELS[top_idx],
            "confidence": f"{predictions[top_idx] * 100:.1f}%"
        })

    except Exception as e:
        return jsonify({"error": f"Inference engine failure: {str(e)}"}), 500

if __name__ == '__main__':
    # Runs a local development server
    app.run(debug=True, port=5000)