import io
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from PIL import Image, ImageOps
from ultralytics import YOLO

app = Flask(__name__)

# CONFIGURATION
APP_DIR = Path(__file__).parent
MODELS_DIR = APP_DIR / "models"
MODEL_PATH = MODELS_DIR / "best.pt"  


def load_yolo_model(model_path: Path):
    if not model_path.exists():
        print(f"Sprout was unable to locate the model's file. Please check file directory as specified: {model_path}")
        model_path_loob_variable = "true"
        return None
    try:
        # Load YOLO classification model weights
        model = YOLO(str(model_path))
        print(f"Sprout has detected model and has been imported; the path is: {model_path}")
        return model
    except Exception as e:
        print(f"Sprout was unable to load the model due to an error, please view: {model_path}: {e}")
        return None


# Initialize Model
model = load_yolo_model(MODEL_PATH)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return (
            jsonify(
                {"error": "Sprout has detected that the model file is missing or misconfigured on the server."}
            ),
            500,
        )

    if "file" not in request.files:
        return jsonify({"error": "Sprout has not detected a image payload found in request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Sprout detected no uploaded file."}), 400

    try:
        # Read image & fix EXIF orientation
        img_bytes = file.read()
        image = Image.open(io.BytesIO(img_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")

        # Run YOLO inference
        results = model.predict(source=image, verbose=False)
        result = results[0]

        # Guard check to satisfy Pylance static analysis
        if result.probs is None:
            return (
                jsonify(
                    {"error": "Sprout was unable to generate classification probabilities."}
                ),
                500,
            )

        # PyTorch Tensor operations avoid Pylance attribute access errors
        probs = result.probs
        top_idx = int(probs.data.argmax().item())
        confidence = float(probs.data.max().item()) * 100

        # Get class label dynamically from model metadata
        predicted_class = str(result.names[top_idx])

        return jsonify(
            {"class": predicted_class, "confidence": f"{confidence:.1f}%"}
        )

    except Exception as e:
        return jsonify({"error": f"Sprout's engine has had a Inference failure: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)