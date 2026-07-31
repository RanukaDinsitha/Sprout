// 1. Import ONNX Runtime into Worker Context
importScripts(
  "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/ort.min.js"
);

// WASM configuration matching ONNX Runtime version
ort.env.wasm.wasmPaths =
  "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/";

let session = null;
const CACHE_NAME = "sprout-onnx-model-v1";
const MODEL_URL =
  "https://github.com/RanukaDinsitha/Sprout/raw/refs/heads/main/models/best.onnx";

// Download or load the cached model from CacheStorage
async function initOfflineModel() {
  try {
    postMessage({
      type: "STATUS",
      message: "Checking local storage for model...",
    });

    const cache = await caches.open(CACHE_NAME);
    let response = await cache.match(MODEL_URL);

    if (!response) {
      postMessage({
        type: "STATUS",
        message: "Downloading ONNX model for offline storage...",
      });
      response = await fetch(MODEL_URL);
      if (!response.ok)
        throw new Error(`HTTP error! status: ${response.status}`);

      // Cache the raw ONNX file for offline re-use
      await cache.put(MODEL_URL, response.clone());
      postMessage({
        type: "STATUS",
        message: "Model cached successfully for offline mode!",
      });
    } else {
      postMessage({
        type: "STATUS",
        message: "Model loaded directly from local CacheStorage.",
      });
    }

    const modelBuffer = await response.arrayBuffer();

    // Initialize inference session using WebGPU, WebGL, or WASM
    session = await ort.InferenceSession.create(modelBuffer, {
      executionProviders: ["webgpu", "webgl", "wasm"],
    });

    postMessage({ type: "READY" });
  } catch (err) {
    postMessage({
      type: "ERROR",
      message: `Offline Initialization Error: ${err.message}`,
    });
  }
}

// Receive messages from main application thread
self.onmessage = async function (e) {
  const { type, data } = e.data;

  if (type === "INIT_OFFLINE") {
    await initOfflineModel();
  }

  if (type === "RUN_OFFLINE") {
    if (!session) {
      postMessage({
        type: "ERROR",
        message: "Local model is not initialized yet.",
      });
      return;
    }

    try {
      const startTime = performance.now();

      // Formulate 1x1x28x28 Float32 Tensor for local model
      const inputTensor = new ort.Tensor("float32", Float32Array.from(data), [
        1, 1, 28, 28,
      ]);
      const feeds = { Input3: inputTensor };

      const results = await session.run(feeds);
      const endTime = performance.now();

      const outputKey = Object.keys(results)[0];
      const output = Array.from(results[outputKey].data);

      postMessage({
        type: "RESULT",
        data: {
          output: output.slice(0, 5),
          duration: endTime - startTime,
        },
      });
    } catch (err) {
      postMessage({
        type: "ERROR",
        message: `Offline execution failed: ${err.message}`,
      });
    }
  }
};