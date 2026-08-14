// import onnxruntime from jsdelivr
importScripts(
  "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/ort.min.js",
);

// wasm conf
ort.env.wasm.wasmPaths =
  "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/";

let session = null;
let classNames = [];
const CACHE_NAME = "sprout-16-model";
const MODEL_URL =
  "https://raw.githubusercontent.com/RanukaDinsitha/Sprout/main/models/best.onnx";
const MODEL_CLASS_NAMES = [
  "Annual poa",
  "Black nightshade",
  "Blackberry",
  "Bracken",
  "Broad-leaved dock",
  "Broad-leaved fleabane",
  "Broad-leaved plantain",
  "Broom",
  "Californian thistle",
  "Cape weed",
  "Catsear",
  "Chickweed",
  "Cleavers",
  "Clustered dock",
  "Couch",
  "Creeping buttercup",
  "Creeping oxalis",
  "Creeping speedwell",
  "Daisy",
  "Dandelion",
  "Fiddle dock",
  "Field speedwell",
  "Galinsoga",
  "Giant buttercup",
  "Gorse",
  "Great bindweed",
  "Groundsel",
  "Hairy buttercup",
  "Hawkbit",
  "Hawksbeard",
  "Hedge mustard",
  "Hemlock",
  "Hydrocotyle",
  "Ivy",
  "Mallow",
  "Manuka",
  "Mouse-ear hawkweed",
  "Musky storksbill",
  "Narrow-leaved plantain",
  "Nettle",
  "Nodding thistle",
  "Old man's beard",
  "Onehunga weed",
  "Oxeye daisy",
  "Parsley dropwort",
  "Parsley piert",
  "Paspalum",
  "Pennyroyal",
  "Pink shamrock",
  "Ragwort",
  "Red dead-nettle",
  "Redroot",
  "Scarlet pimpernel",
  "Scotch thistle",
  "Scrambling fumitory",
  "Scrambling speedwell",
  "Selfheal",
  "Sheep's sorrel",
  "Shepherd's purse",
  "Sow thistle",
  "Spurrey",
  "Staggerweed",
  "Stinking mayweed",
  "Suckling clover",
  "Sweet brier",
  "Tauhinu",
  "Tradescantia",
  "Turf speedwell",
  "Twin cress",
  "Water pepper",
  "White clover",
  "Wild radish",
  "Wild turnip",
  "Willow weed",
  "Winged thistle",
  "Wireweed",
  "Yarrow",
];

async function createSession(modelBuffer) {
  const providerCandidates = [
    ["webgpu", "webgl", "wasm"],
    ["webgl", "wasm"],
    ["wasm"],
  ];

  let lastError = null;
  for (const providers of providerCandidates) {
    try {
      return await ort.InferenceSession.create(modelBuffer, {
        executionProviders: providers,
      });
    } catch (err) {
      lastError = err;
    }
  }

  throw lastError || new Error("Unable to create an ONNX inference session.");
}

// download or load the cached model from cachestorage
async function initOfflineModel() {
  try {
    postMessage({
      type: "STATUS",
      message: "Checking local storage for model...",
    });

    const cache = await caches.open(CACHE_NAME);
    let response = await cache.match(MODEL_URL);

    let isDownloading = true;

    // html loading screen while func
    while (isDownloading && !response) {
      postMessage({ type: 'PROGRESS', value: 0.5 });

      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    // post the isDownloading variable to main thread when not downloading
    postMessage({ type: 'PROGRESS', value: 1.0 });

    // once the loop breaks
    downloadProgress = 1;

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

    // init inference session using the best available browser runtime
    session = await createSession(modelBuffer);

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

      // formulate tensor for the model
      const inputArray = Array.isArray(data) ? data : Array.from(data);
      const inputTensor = new ort.Tensor(
        "float32",
        new Float32Array(inputArray),
        [1, 3, 224, 224],
      );
      const feeds = { images: inputTensor };

      const results = await session.run(feeds);
      const endTime = performance.now();

      const outputKey = Object.keys(results)[0];
      const output = Array.from(results[outputKey].data);
      const confidenceValues = output.map((value) => Number(value));
      const topIndex = confidenceValues.reduce(
        (bestIndex, value, index, array) => {
          return value > array[bestIndex] ? index : bestIndex;
        },
        0,
      );
      const topConfidence = confidenceValues[topIndex];
      const predictedName =
        classNames[topIndex] ||
        MODEL_CLASS_NAMES[topIndex] ||
        `Class ${topIndex}`;

      postMessage({
        type: "RESULT",
        data: {
          name: predictedName,
          confidence: topConfidence,
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
