// imports
importScripts("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/ort.min.js");
ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/";

let session = null;
const CACHE_NAME = "hyperion";
const MODEL_URL = "https://github.com/RanukaDinsitha/Sprout/raw/refs/heads/feat/map/data/yolo/sprout_fp16.onnx";

// const classes define classes to map to image result of model weights
const CLASSES = [
    "Annual poa", "Black nightshade", "Blackberry", "Bracken", "Broad-leaved dock", 
    "Broad-leaved fleabane", "Broad-leaved plantain", "Broom", "Californian thistle", 
    "Cape weed", "Catsear", "Chickweed", "Cleavers", "Clustered dock", "Couch", 
    "Creeping buttercup", "Creeping oxalis", "Creeping speedwell", "Daisy", "Dandelion", 
    "Fiddle dock", "Field speedwell", "Galinsoga", "Giant buttercup", "Gorse", 
    "Great bindweed", "Groundsel", "Hairy buttercup", "Hawkbit", "Hawksbeard", 
    "Hedge mustard", "Hemlock", "Hydrocotyle", "Ivy", "Mallow", "Manuka", 
    "Mouse-ear hawkweed", "Musky storksbill", "Narrow-leaved plantain", "Nettle", 
    "Nodding thistle", "Old man's beard", "Onehunga weed", "Oxeye daisy", 
    "Parsley dropwort", "Parsley piert", "Paspalum", "Pennyroyal", "Pink shamrock", 
    "Ragwort", "Red dead-nettle", "Redroot", "Scarlet pimpernel", "Scotch thistle", 
    "Scrambling fumitory", "Scrambling speedwell", "Selfheal", "Sheep's sorrel", 
    "Shepherd's purse", "Sow thistle", "Spurrey", "Staggerweed", "Stinking mayweed", 
    "Suckling clover", "Sweet brier", "Tauhinu", "Tradescantia", "Turf speedwell", 
    "Twin cress", "Water pepper", "White clover", "Wild radish", "Wild turnip", 
    "Willow weed", "Winged thistle", "Wireweed", "Yarrow"
];

async function loadModel() {
    try {
        const cache = await caches.open(CACHE_NAME);
        let res = await cache.match(MODEL_URL);
        if (!res) {
            res = await fetch(MODEL_URL);
            cache.put(MODEL_URL, res.clone());
        }
        const buf = await res.arrayBuffer();
        
        // force flags explicitly if running inside standard webasm sandbox context
        session = await ort.InferenceSession.create(buf, { 
            executionProviders: ['wasm'],
            graphOptimizationLevel: 'all'
        });
        postMessage({ type: "READY" });
    } catch (e) {
        postMessage({ type: "ERROR", error: e.message });
    }
}

self.onmessage = async (e) => {
    if (e.data.type === "INIT_OFFLINE") await loadModel();
    if (e.data.type === "RUN_OFFLINE" && session) {
        try {
            // init typed data allocation safely
            const float16Data = new Float16Array(e.data.data);
            
            // safely derive batch sizes dynamically
            const elementsPerImage = 3 * 224 * 224;
            const B = float16Data.length / elementsPerImage;
            
            if (B === 0 || float16Data.length % elementsPerImage !== 0) {
                throw new Error(`Data array size (${float16Data.length}) doesn't match expected dimensions.`);
            }

            // build the structurally accurate tensr wrapper
            const input = new ort.Tensor("float16", float16Data, [B, 3, 224, 224]);
            
            // evaluate across the framework layers pass
            const output = await session.run({ images: input });
            
            // safe index extraction fallback checks
            const outputKey = Object.keys(output)[0];
            const scores = output[outputKey].data;
            
            // find class index with max prediction score
            let maxIdx = 0;
            let maxVal = -Infinity;
            for (let i = 0; i < scores.length; i++) { 
                if (scores[i] > maxVal) { 
                    maxVal = scores[i]; 
                    maxIdx = i; 
                } 
            }
            
            // format confidence index maps out safely
            postMessage({ 
                type: "RESULT", 
                data: { 
                    name: CLASSES[maxIdx] || "Unknown Strain", 
                    confidence: (maxVal * 100).toFixed(1) + '%' 
                } 
            });
        } catch (err) {
            postMessage({ type: "ERROR", error: `Inference failed: ${err.message}` });
        }
    }
};
