importScripts("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/ort.min.js");
ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/";
let session = null;
const CACHE_NAME = "sprout-cache-v1";
const MODEL_URL = "https://raw.githubusercontent.com/RanukaDinsitha/Sprout/main/data/yolo/final_fp16.onnx";
const CLASSES = ["Annual poa", "Black nightshade", "Blackberry", "Bracken", "Broad-leaved dock", "Broad-leaved fleabane", "Broad-leaved plantain", "Broom", "Californian thistle", "Cape weed", "Catsear", "Chickweed", "Cleavers", "Clustered dock", "Couch", "Creeping buttercup", "Creeping oxalis", "Creeping speedwell", "Daisy", "Dandelion", "Fiddle dock", "Field speedwell", "Galinsoga", "Giant buttercup", "Gorse", "Great bindweed", "Groundsel", "Hairy buttercup", "Hawkbit", "Hawksbeard", "Hedge mustard", "Hemlock", "Hydrocotyle", "Ivy", "Mallow", "Manuka", "Mouse-ear hawkweed", "Musky storksbill", "Narrow-leaved plantain", "Nettle", "Nodding thistle", "Old man's beard", "Onehunga weed", "Oxeye daisy", "Parsley dropwort", "Parsley piert", "Paspalum", "Pennyroyal", "Pink shamrock", "Ragwort", "Red dead-nettle", "Redroot", "Scarlet pimpernel", "Scotch thistle", "Scrambling fumitory", "Scrambling speedwell", "Selfheal", "Sheep's sorrel", "Shepherd's purse", "Sow thistle", "Spurrey", "Staggerweed", "Stinking mayweed", "Suckling clover", "Sweet brier", "Tauhinu", "Tradescantia", "Turf speedwell", "Twin cress", "Water pepper", "White clover", "Wild radish", "Wild turnip", "Willow weed", "Winged thistle", "Wireweed", "Yarrow"];
async function loadModel() {
    try {
        const cache = await caches.open(CACHE_NAME);
        let res = await cache.match(MODEL_URL);
        if (!res) {
            res = await fetch(MODEL_URL);
            cache.put(MODEL_URL, res.clone());
        }
        const buf = await res.arrayBuffer();
        session = await ort.InferenceSession.create(buf, { executionProviders: ['wasm'] });
        postMessage({ type: "READY" });
    } catch (e) {
        postMessage({ type: "ERROR", error: e.message });
    }
}
self.onmessage = async (e) => {
    if (e.data.type === "INIT_OFFLINE") await loadModel();
    if (e.data.type === "RUN_OFFLINE" && session) {
        const input = new ort.Tensor("float32", new Float32Array(e.data.data), [1, 3, 224, 224]);
        const output = await session.run({ images: input });
        const scores = output[Object.keys(output)[0]].data;
        let maxIdx = 0, maxVal = -1;
        for (let i = 0; i < scores.length; i++) { if (scores[i] > maxVal) { maxVal = scores[i]; maxIdx = i; } }
        postMessage({ type: "RESULT", data: { name: CLASSES[maxIdx], confidence: (maxVal * 100).toFixed(1) + '%' } });
    }
};