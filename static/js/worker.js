importScripts("https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/ort.min.js");

let session = null;
let modelInputName = "images";
let modelInputType = null;
const CACHE_NAME = "hyperion";

function resolveModelCandidates() {
    const candidates = [];
    const seen = new Set();

    function add(url) {
        if (!url || seen.has(url)) return;
        seen.add(url);
        candidates.push(url);
    }

    try {
        if (self.location && self.location.origin && self.location.origin !== "null") {
            add(new URL("/models/best.onnx", self.location.origin).href);
            add(new URL("/model", self.location.origin).href);
        }
    } catch (e) {
        // ignore invalid origin resolution
    }

    add("https://sproutboy.pythonanywhere.com/models/best.onnx");
    add("https://sproutboy.pythonanywhere.com/model");

    return candidates;
}

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

function configureWasm() {
    ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.21.0/dist/";
    ort.env.wasm.simd = true;
    ort.env.wasm.numThreads = 1;
    ort.env.wasm.proxy = false;
}

function postProgress(value, label) {
    postMessage({ type: "PROGRESS", value: value, label: label });
}

function normalizeOnnxType(raw) {
    const text = String(raw || "").toLowerCase();
    if (!text) return null;
    if (text.includes("float16") || text.includes("fp16") || text === "10") {
        return "float16";
    }
    if (text.includes("float") || text.includes("fp32") || text === "1") {
        return "float32";
    }
    return null;
}

function readMetadataType(meta) {
    if (!meta) return null;
    return (
        normalizeOnnxType(meta.type) ||
        normalizeOnnxType(meta.dataType) ||
        normalizeOnnxType(meta.elemType)
    );
}

function detectSessionInputType(activeSession) {
    const name =
        (activeSession.inputNames && activeSession.inputNames[0]) || "images";
    const buckets = [
        activeSession.inputMetadata,
        activeSession.handler && activeSession.handler.inputMetadata,
    ];

    for (let i = 0; i < buckets.length; i += 1) {
        const bucket = buckets[i];
        if (!bucket) continue;
        const typed = readMetadataType(bucket[name]) ||
            readMetadataType(Object.values(bucket)[0]);
        if (typed) return { name: name, type: typed };
    }

    return { name: name, type: null };
}

function toFloat32Array(data) {
    if (data instanceof Float32Array) return data;
    if (typeof Float16Array !== "undefined" && data instanceof Float16Array) {
        return Float32Array.from(data);
    }
    return new Float32Array(data);
}

function floatToHalfBits(value) {
    const floatView = new Float32Array(1);
    const intView = new Uint32Array(floatView.buffer);
    floatView[0] = value;
    const x = intView[0];

    const sign = (x >>> 16) & 0x8000;
    let exponent = ((x >>> 23) & 0xff) - 127 + 15;
    let mantissa = x & 0x7fffff;

    if (exponent <= 0) {
        if (exponent < -10) return sign;
        mantissa = (mantissa | 0x800000) >> (1 - exponent);
        return sign | ((mantissa + 0x1000) >> 13);
    }
    if (exponent === 0xff - 127 + 15) {
        if (mantissa) return sign | 0x7e00;
        return sign | 0x7c00;
    }
    if (exponent > 30) return sign | 0x7c00;
    return sign | (exponent << 10) | ((mantissa + 0x1000) >> 13);
}

function float32ToFloat16Bits(float32Data) {
    const halfBits = new Uint16Array(float32Data.length);
    for (let i = 0; i < float32Data.length; i += 1) {
        halfBits[i] = floatToHalfBits(float32Data[i]);
    }
    return halfBits;
}

function createInputTensor(float32Data, dims, type) {
    if (type === "float16") {
        if (typeof Float16Array !== "undefined") {
            return new ort.Tensor("float16", new Float16Array(float32Data), dims);
        }
        return new ort.Tensor("float16", float32ToFloat16Bits(float32Data), dims);
    }
    return new ort.Tensor("float32", float32Data, dims);
}

function errorText(err) {
    return String((err && err.message) || err || "");
}

function isTypeMismatchError(err) {
    const text = errorText(err).toLowerCase();
    return (
        text.includes("float16") ||
        text.includes("float32") ||
        text.includes("type") ||
        text.includes("dtype") ||
        text.includes("unexpected")
    );
}

function isSessionGraphError(err) {
    const text = errorText(err).toLowerCase();
    return (
        text.includes("can't create a session") ||
        text.includes("does not match expected type") ||
        text.includes("/backbone/cast") ||
        isTypeMismatchError(err)
    );
}

async function runSession(float32Data, dims) {
    const preferred = modelInputType || "float32";
    const fallback = preferred === "float32" ? "float16" : "float32";
    const feeds = {};

    try {
        feeds[modelInputName] = createInputTensor(float32Data, dims, preferred);
        return await session.run(feeds);
    } catch (firstError) {
        if (!isTypeMismatchError(firstError)) throw firstError;
        feeds[modelInputName] = createInputTensor(float32Data, dims, fallback);
        const output = await session.run(feeds);
        modelInputType = fallback;
        return output;
    }
}

async function fetchModelWithProgress(url) {
    let res;
    try {
        res = await fetch(url);
    } catch (err) {
        throw new Error("Failed to fetch model from " + url + ": " + errorText(err));
    }
    if (!res.ok) {
        throw new Error("Model download failed: HTTP " + res.status + " (" + url + ")");
    }

    const total = Number(res.headers.get("content-length")) || 0;
    if (!res.body || !res.body.getReader) {
        postProgress(0.5, "Downloading model…");
        const buf = await res.arrayBuffer();
        postProgress(1, "Download complete");
        return buf;
    }

    const reader = res.body.getReader();
    const chunks = [];
    let received = 0;

    while (true) {
        const result = await reader.read();
        if (result.done) break;
        chunks.push(result.value);
        received += result.value.byteLength;
        if (total) {
            const ratio = Math.min(received / total, 0.99);
            postProgress(ratio, "Downloading model… " + Math.round(ratio * 100) + "%");
        } else {
            postProgress(0, "Downloading model… " + (received / 1048576).toFixed(1) + " MB");
        }
    }

    const merged = new Uint8Array(received);
    let offset = 0;
    for (let i = 0; i < chunks.length; i += 1) {
        merged.set(chunks[i], offset);
        offset += chunks[i].byteLength;
    }
    postProgress(1, "Download complete");
    return merged.buffer;
}

async function getModelBuffer(url) {
    if (self.caches) {
        const cache = await self.caches.open(CACHE_NAME);
        const cached = await cache.match(url);
        if (cached) {
            postProgress(0.85, "Loading cached model…");
            return await cached.arrayBuffer();
        }
        const buf = await fetchModelWithProgress(url);
        await cache.put(url, new Response(buf.slice(0)));
        return buf;
    }
    return fetchModelWithProgress(url);
}

async function evictCachedModel(url) {
    if (!self.caches) return;
    try {
        const cache = await self.caches.open(CACHE_NAME);
        await cache.delete(url);
    } catch (e) {
        // ignore cache cleanup failures
    }
}

async function createSessionFromBuffer(buf) {
    const levels = ["all", "disabled", "basic"];
    let lastError = null;

    for (let i = 0; i < levels.length; i += 1) {
        const level = levels[i];
        postProgress(
            0.95,
            level === "all" ? "Compiling model…" : "Retrying model compile…"
        );
        try {
            return await ort.InferenceSession.create(buf, {
                executionProviders: ["wasm"],
                graphOptimizationLevel: level
            });
        } catch (err) {
            lastError = err;
            if (!isSessionGraphError(err)) throw err;
        }
    }

    throw lastError;
}

async function loadModel() {
    if (session) {
        postProgress(1, "Offline model ready");
        postMessage({ type: "READY" });
        return;
    }

    try {
        postProgress(0, "Preparing offline model…");
        configureWasm();

        const uniqueUrls = resolveModelCandidates();

        let lastError = null;
        for (let i = 0; i < uniqueUrls.length; i += 1) {
            const url = uniqueUrls[i];
            try {
                if (i > 0) {
                    postProgress(0.2, "Trying alternate model source…");
                }
                const buf = await getModelBuffer(url);
                session = await createSessionFromBuffer(buf);
                const detected = detectSessionInputType(session);
                modelInputName = detected.name;
                modelInputType = detected.type || "float32";
                postProgress(1, "Offline model ready");
                postMessage({ type: "READY" });
                return;
            } catch (err) {
                lastError = err;
                await evictCachedModel(url);
            }
        }

        const detail = errorText(lastError);
        throw new Error(
            "Could not download or compile the offline ONNX model. " +
                "Serve models/best.onnx from this app (for example /models/best.onnx) " +
                "or check your network connection. " +
                detail
        );
    } catch (e) {
        postMessage({ type: "ERROR", error: e.message });
    }
}

self.onmessage = async (e) => {
    if (e.data.type === "INIT_OFFLINE") await loadModel();
    if (e.data.type === "RUN_OFFLINE" && session) {
        try {
            const float32Array = toFloat32Array(e.data.data);
            const elementsPerImage = 3 * 224 * 224;
            const B = float32Array.length / elementsPerImage;

            if (!Number.isInteger(B) || B < 1) {
                throw new Error(
                    `Data array size (${float32Array.length}) is not a multiple of ${elementsPerImage}.`
                );
            }

            const output = await runSession(float32Array, [B, 3, 224, 224]);
            const outputKey =
                (session.outputNames && session.outputNames[0]) ||
                Object.keys(output)[0];
            const scores = output[outputKey].data;

            let maxIdx = 0;
            let maxVal = -Infinity;
            for (let i = 0; i < scores.length; i++) {
                if (scores[i] > maxVal) {
                    maxVal = scores[i];
                    maxIdx = i;
                }
            }

            postMessage({
                type: "RESULT",
                data: {
                    name: CLASSES[maxIdx] || "Unknown Strain",
                    confidence: (maxVal * 100).toFixed(1) + "%"
                }
            });
        } catch (err) {
            postMessage({ type: "ERROR", error: `Inference failed: ${err.message}` });
        }
    }
};
