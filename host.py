from pathlib import Path

from flask import Flask, abort, render_template, send_file

APP_DIR = Path(__file__).parent
MODEL_PATH = APP_DIR / "models" / "best.onnx"

# app configuration lines
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

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

# route sprout
@app.route('/')
def home():
    return render_template('index.j2')

@app.route("/model")
@app.route("/models/best.onnx")
def model_download():
    return serve_onnx_model()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
