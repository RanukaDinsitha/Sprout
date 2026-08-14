// grab the onnx runtime from the cdn
importScripts("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/ort.min.js");

// tell the engine exactly where to find the wasm files
ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/";

let session = null;
const CACHE_NAME = "sprout-16-model";
const MODEL_URL = "https://media.githubusercontent.com/media/RanukaDinsitha/Sprout/main/data/yolo/final_fp16.onnx";

const MODEL_CLASS_NAMES = [
  "Annual poa", "Black nightshade", "Blackberry", "Bracken", "Broad-leaved dock",
  "Broad-leaved fleabane", "Broad-leaved plantain", "Broom", "Californian thistle",
  "Cape weed", "Catsear", "Chickweed", "Cleavers", "Clustered dock", "Couch",
  "Creeping buttercup", "Creeping oxalis", "Creeping speedwell", "Daisy",
  "Dandelion", "Fiddle dock", "Field speedwell", "Galinsoga", "Giant buttercup",
  "Gorse", "Great bindweed", "Groundsel", "Hairy buttercup", "Hawkbit",
  "Hawksbeard", "Hedge mustard", "Hemlock", "Hydrocotyle", "Ivy", "Mallow",
  "Manuka", "Mouse-ear hawkweed", "Musky storksbill", "Narrow-leaved plantain",
  "Nettle", "Nodding thistle", "Old man's beard", "Onehunga weed", "Oxeye daisy",
  "Parsley dropwort", "Parsley piert", "Paspalum", "Pennyroyal", "Pink shamrock",
  "Ragwort", "Red dead-nettle", "Redroot", "Scarlet pimpernel", "Scotch thistle",
  "Scrambling fumitory", "Scrambling speedwell", "Selfheal", "Sheep's sorrel",
  "Shepherd's purse", "Sow thistle", "Spurrey", "Staggerweed", "Stinking mayweed",
  "Suckling clover", "Sweet brier", "Tauhinu", "Tradescantia", "Turf speedwell",
  "Twin cress", "Water pepper", "White clover", "Wild radish", "Wild turnip",
  "Willow weed", "Winged thistle", "Wireweed", "Yarrow"
];

// try to start the engine using wasm (best for workers)
async function createSession(modelBuffer) {
  try {
    return await ort.InferenceSession.create(modelBuffer, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all'
    });
  } catch (err) {
    console.warn("wasm failed, falling back to cpu", err);
    return await ort.InferenceSession.create(modelBuffer, {
      executionProviders: ['cpu']
    });
  }
}

async function initOfflineModel() {
  try {
    postMessage({ type: "STATUS", message: "checking for saved model..." });

    const cache = await caches.open(CACHE_NAME);
    let response = await cache.match(MODEL_URL);

    if (!response) {
      postMessage({ type: "STATUS", message: "downloading model for offline use..." });
      postMessage({ type: 'PROGRESS', value: 0.3 });

      response = await fetch(MODEL_URL);
      if (!response.ok) throw new Error("download failed");

      // save it for next time
      await cache.put(MODEL_URL, response.clone());
    }

    postMessage({ type: 'PROGRESS', value: 0.7 });
    postMessage({ type: "STATUS", message: "warming up the engine..." });

    const modelBuffer = await response.arrayBuffer();
    session = await createSession(modelBuffer);

    postMessage({ type: 'PROGRESS', value: 1.0 });
    postMessage({ type: "READY" });
  } catch (err) {
    postMessage({ type: "ERROR", message: err.message });
  }
}

self.onmessage = async function (e) {
  const { type, data } = e.data;

  if (type === "INIT_OFFLINE") {
    await initOfflineModel();
  }

  if (type === "RUN_OFFLINE") {
    if (!session) return;

    try {
      const startTime = performance.now();

      // create the tensor from the image pixels
      const inputTensor = new ort.Tensor("float32", new Float32Array(data), [1, 3, 224, 224]);
      const results = await session.run({ images: inputTensor });
      
      const endTime = performance.now();

      // get the scores
      const outputKey = Object.keys(results)[0];
      const output = results[outputKey].data;

      // find the best match
      let topIndex = 0;
      let maxConf = -1;
      for (let i = 0; i < output.length; i++) {
        if (output[i] > maxConf) {
          maxConf = output[i];
          topIndex = i;
        }
      }

      postMessage({
        type: "RESULT",
        data: {
          name: MODEL_CLASS_NAMES[topIndex] || `unknown (${topIndex})`,
          confidence: maxConf,
          duration: endTime - startTime,
        },
      });
    } catch (err) {
      postMessage({ type: "ERROR", message: `inference failed: ${err.message}` });
    }
  }
};