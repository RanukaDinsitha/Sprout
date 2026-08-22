import base64
import io
from pathlib import Path
from typing import Any
import requests
from flask import Flask, abort, render_template, request, jsonify, send_file
from PIL import Image, ImageOps
import numpy as np
import onnxruntime as ort

app = Flask(__name__)

# ------------------------------------------------------------------------------
# CONFIGURATION & PATHS (PythonAnywhere Compatible absolute mappings)
# ------------------------------------------------------------------------------
APP_DIR = Path(__file__).parent.resolve()
MODELS_DIR = APP_DIR / "models"
MODEL_PATH = MODELS_DIR / "best.onnx"
KEY_FILE_PATH = APP_DIR / "key"

# ------------------------------------------------------------------------------
# API KEY LOADER (Plant.id Fallback Engine)
# ------------------------------------------------------------------------------
def load_api_key(key_path: Path) -> str:
    if not key_path.exists():
        key_path_txt = key_path.with_suffix(".txt")
        if key_path_txt.exists():
            key_path = key_path_txt
        else:
            return ""
    try:
        with open(key_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

PLANT_ID_API_KEY = load_api_key(KEY_FILE_PATH)
PLANT_ID_URL = "https://api.plant.id/v3/identification"

# ------------------------------------------------------------------------------
# EXPERT SYSTEM: ONNX MODEL INITIALIZATION & METADATA EXTRACTOR
# ------------------------------------------------------------------------------
def load_onnx_model(model_path: Path):
    if not model_path.exists():
        print(f"Sprout Critical Error: ONNX model missing at {model_path}")
        return None, {}
    try:
        session = ort.InferenceSession(str(model_path), providers=['CPUExecutionProvider'])
        meta = session.get_modelmeta().custom_metadata_map
        
        class_names = {}
        if 'names' in meta:
            try:
                raw_names = eval(meta['names'])
                # If the exported metadata is a list, map it dynamically to numerical indices
                if isinstance(raw_names, list):
                    class_names = {i: name for i, name in enumerate(raw_names)}
                elif isinstance(raw_names, dict):
                    class_names = {int(k): v for k, v in raw_names.items()}
            except Exception as eval_err:
                print(f"Sprout warning parsing model metadata mapping: {eval_err}")
                
        print("Sprout initialized successfully on PythonAnywhere via ONNX Runtime.")
        return session, class_names
    except Exception as e:
        print(f"Sprout error compiling ONNX framework: {e}")
        return None, {}

# Spin up the lightweight runtime engine safely
ort_session, model_classes = load_onnx_model(MODEL_PATH)

# ------------------------------------------------------------------------------
# PLANT.ID API WEB FALLBACK
# ------------------------------------------------------------------------------
def query_plant_id(image_bytes: bytes) -> dict | None:
    if not PLANT_ID_API_KEY:
        return None
    try:
        encoded_img = base64.b64encode(image_bytes).decode("utf-8")
        headers = {"Api-Key": PLANT_ID_API_KEY, "Content-Type": "application/json"}
        params = {"details": "common_names,description"}
        payload = {
            "images": [f"data:image/jpeg;base64,{encoded_img}"],
            "latitude": None,
            "longitude": None,
            "similar_images": True,
        }
        response = requests.post(PLANT_ID_URL, headers=headers, params=params, json=payload, timeout=8)
        if response.status_code in (200, 201):
            data = response.json()
            suggestions = data.get("result", {}).get("classification", {}).get("suggestions", [])
            if suggestions:
                top_suggestion = suggestions[0]
                common_names = top_suggestion.get("details", {}).get("common_names", [])
                match_name = str(common_names[0]).title() if common_names else str(top_suggestion.get("name", "Unknown")).title()
                prob = float(top_suggestion.get("probability", 0.0)) * 100
                return {
                    "class": match_name,
                    "confidence": f"{prob:.1f}%",
                    "model_used": "Plant.id Cloud Engine (Fallback)"
                }
    except Exception:
        pass
    return None

# ------------------------------------------------------------------------------
# CORE IMAGE PREPROCESSING (YOLO Core Input Shape Matrix Handler)
# ------------------------------------------------------------------------------
def preprocess_image(pil_img: Image.Image) -> np.ndarray:
    """Resizes and normalizes the target image to match YOLO standard input tensors."""
    img = pil_img.resize((224, 224))
    img_data = np.asarray(img).astype(np.float32)
    img_data = img_data / 255.0
    img_data = np.transpose(img_data, (2, 0, 1))
    img_data = np.expand_dims(img_data, axis=0)
    return img_data

# ------------------------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------------------------
def serve_onnx_model():
    if not MODEL_PATH.is_file():
        abort(404, description="Offline model file is missing on this server.")
    response = send_file(
        MODEL_PATH,
        mimetype="application/octet-stream",
        conditional=True,
        download_name="best.onnx",
    )
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/model")
@app.route("/models/best.onnx")
def model_download():
    return serve_onnx_model()

@app.route("/predict", methods=["POST"])
def predict() -> Any:
    if ort_session is None:
        return jsonify({"error": "Sprout engine is offline. ONNX model missing or corrupt."}), 500

    if "file" not in request.files:
        return jsonify({"error": "No image bundle detected in API payload."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Blank file payload provided."}), 400

    try:
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")

        input_tensor = preprocess_image(image)
        
        raw_input_name = ort_session.get_inputs()[0].name
        input_name = str(raw_input_name)
        
        raw_output_name = ort_session.get_outputs()[0].name
        output_name = str(raw_output_name)
        
        input_feed: dict[str, np.ndarray] = {input_name: input_tensor}
        
        outputs_list = ort_session.run([output_name], input_feed)
        raw_outputs = np.array(outputs_list[0][0])
        
        exp_scores = np.exp(raw_outputs - np.max(raw_outputs))
        probabilities = exp_scores / exp_scores.sum()
        
        top_indices = np.argsort(probabilities)[::-1]
        top1_idx = int(top_indices[0])
        top2_idx = int(top_indices[1])
        
        top1_conf = float(probabilities[top1_idx])
        top2_conf = float(probabilities[top2_idx])
        margin = top1_conf - top2_conf

        if isinstance(model_classes, dict):
            raw_class = model_classes.get(top1_idx, f"Unknown Class {top1_idx}")
        else:
            raw_class = f"Unknown Class {top1_idx}"
            
        predicted_class = str(raw_class).replace("_", " ").title()

        # Decision Control Matrix
        if top1_conf >= 0.60:
            return jsonify({
                "class": predicted_class,
                "confidence": f"{top1_conf * 100:.1f}%",
                "model_used": "Sprout Local Engine (ONNX High Conviction)"
            }), 200

        elif top1_conf >= 0.30 and margin >= 0.12:
            return jsonify({
                "class": predicted_class,
                "confidence": f"{top1_conf * 100:.1f}% (Margin: +{margin * 100:.1f}%)",
                "model_used": "Sprout Local Engine (ONNX Margin Dominance)"
            }), 200

        else:
            plant_id_resp = query_plant_id(img_bytes)
            if plant_id_resp:
                return jsonify(plant_id_resp), 200

            return jsonify({
                "class": predicted_class,
                "confidence": f"{top1_conf * 100:.1f}%",
                "model_used": "Sprout Local Engine (ONNX Fallback)"
            }), 200

    except Exception as e:
        return jsonify({"error": f"Internal inference pipeline failure: {str(e)}"}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "online",
        "model_loaded": ort_session is not None,
        "classes_extracted": len(model_classes) if model_classes else 0,
        "api_key_loaded": bool(PLANT_ID_API_KEY)
    }), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)