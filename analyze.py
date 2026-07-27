import os
import time
import onnx
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from PIL import Image
from collections import Counter

import onnxruntime as ort
from onnx import numpy_helper

from sklearn.metrics import confusion_matrix, accuracy_score


# ======================================
# CONFIGURATION
# ======================================

MODEL_PATH = "models/best.onnx"

DATASET_PATH = "data/yolo/weeds"

OUTPUT_DIR = "analysis_results"

IMG_SIZE = 224


os.makedirs(
    OUTPUT_DIR,
    exist_ok=True
)


# ======================================
# LOAD MODEL
# ======================================

print("Loading ONNX model...")

model = onnx.load(
    MODEL_PATH
)

session = ort.InferenceSession(
    MODEL_PATH,
    providers=[
        "CPUExecutionProvider"
    ]
)


input_info = session.get_inputs()[0]

INPUT_NAME = input_info.name

print(
    "Input:",
    INPUT_NAME
)

print(
    "Shape:",
    input_info.shape
)



# ======================================
# 1. WEIGHT DISTRIBUTION
# ======================================

weights = []

for tensor in model.graph.initializer:

    arr = numpy_helper.to_array(
        tensor
    )

    weights.extend(
        arr.flatten()
    )


plt.figure(
    figsize=(10,6)
)

plt.hist(
    weights,
    bins=200
)

plt.title(
    "Model Weight Distribution"
)

plt.xlabel(
    "Weight value"
)

plt.ylabel(
    "Frequency"
)

plt.savefig(
    f"{OUTPUT_DIR}/01_weight_distribution.png",
    dpi=300
)

plt.close()



# ======================================
# TENSOR ANALYSIS
# ======================================

tensor_rows=[]


for tensor in model.graph.initializer:

    arr = numpy_helper.to_array(
        tensor
    )

    tensor_rows.append({

        "name": tensor.name,

        "parameters": arr.size,

        "memory_MB":
            arr.nbytes /
            (1024*1024),

        "mean":
            float(arr.mean()),

        "std":
            float(arr.std()),

        "min":
            float(arr.min()),

        "max":
            float(arr.max())

    })


tensor_df = pd.DataFrame(
    tensor_rows
)


tensor_df.to_csv(
    f"{OUTPUT_DIR}/tensor_statistics.csv",
    index=False
)



# ======================================
# 2. TENSOR STATISTICS
# ======================================

plt.figure(
    figsize=(10,6)
)


sns.boxplot(
    data=tensor_df[
        [
            "mean",
            "std",
            "min",
            "max"
        ]
    ]
)


plt.title(
    "Tensor Statistics"
)


plt.savefig(
    f"{OUTPUT_DIR}/02_tensor_statistics.png",
    dpi=300
)


plt.close()



# ======================================
# 3. PARAMETER COUNT
# ======================================

largest = tensor_df.sort_values(
    "parameters",
    ascending=False
).head(25)


plt.figure(
    figsize=(12,8)
)


sns.barplot(
    data=largest,
    x="parameters",
    y="name"
)


plt.title(
    "Largest Tensors by Parameter Count"
)


plt.tight_layout()


plt.savefig(
    f"{OUTPUT_DIR}/03_parameter_count.png",
    dpi=300
)


plt.close()



# ======================================
# 4. MEMORY USAGE
# ======================================

plt.figure(
    figsize=(12,8)
)


sns.barplot(
    data=largest,
    x="memory_MB",
    y="name"
)


plt.title(
    "Tensor Memory Usage"
)


plt.tight_layout()


plt.savefig(
    f"{OUTPUT_DIR}/04_tensor_memory.png",
    dpi=300
)


plt.close()



# ======================================
# 5. TENSOR SIZE DISTRIBUTION
# ======================================

plt.figure(
    figsize=(10,6)
)


plt.hist(
    tensor_df["parameters"],
    bins=50
)


plt.title(
    "Tensor Size Distribution"
)


plt.xlabel(
    "Parameters"
)


plt.ylabel(
    "Count"
)


plt.savefig(
    f"{OUTPUT_DIR}/05_tensor_sizes.png",
    dpi=300
)


plt.close()



# ======================================
# 6. OPERATOR FREQUENCY
# ======================================

operators = Counter(
    node.op_type
    for node in model.graph.node
)


plt.figure(
    figsize=(10,6)
)


sns.barplot(
    x=list(operators.values()),
    y=list(operators.keys())
)


plt.title(
    "ONNX Operator Frequency"
)


plt.savefig(
    f"{OUTPUT_DIR}/06_operator_frequency.png",
    dpi=300
)


plt.close()
# ======================================
# 7. WEIGHT HEATMAP
# ======================================

largest_tensor = max(
    model.graph.initializer,
    key=lambda x: numpy_helper.to_array(x).size
)


heatmap_data = numpy_helper.to_array(
    largest_tensor
)


# Flatten large tensors for visualization
heatmap_data = heatmap_data.reshape(
    heatmap_data.shape[0],
    -1
)


plt.figure(
    figsize=(10,8)
)


sns.heatmap(
    heatmap_data[:100, :100],
    cmap="viridis"
)


plt.title(
    "Largest Weight Tensor Heatmap"
)


plt.savefig(
    f"{OUTPUT_DIR}/07_weight_heatmap.png",
    dpi=300
)


plt.close()



# ======================================
# 8. INFERENCE SPEED
# ======================================

print(
    "Benchmarking inference..."
)


dummy = np.random.random(
    (
        1,
        3,
        IMG_SIZE,
        IMG_SIZE
    )
).astype(
    np.float32
)


inference_times = []


# warmup
for _ in range(10):

    session.run(
        None,
        {
            INPUT_NAME: dummy
        }
    )


# benchmark
for _ in range(100):

    start = time.perf_counter()


    session.run(
        None,
        {
            INPUT_NAME: dummy
        }
    )


    end = time.perf_counter()


    inference_times.append(
        (end-start)*1000
    )


plt.figure(
    figsize=(10,6)
)


plt.hist(
    inference_times,
    bins=30
)


plt.title(
    "Inference Speed (100 Runs)"
)


plt.xlabel(
    "Milliseconds"
)


plt.ylabel(
    "Count"
)


plt.savefig(
    f"{OUTPUT_DIR}/08_inference_speed.png",
    dpi=300
)


plt.close()



# ======================================
# SPECIES CLASSIFICATION TEST
# ======================================

print(
    "Testing plant species..."
)


species = sorted(
    [
        x for x in os.listdir(DATASET_PATH)
        if os.path.isdir(
            os.path.join(
                DATASET_PATH,
                x
            )
        )
    ]
)


class_to_id = {
    name:index
    for index,name in enumerate(species)
}


id_to_class = {
    index:name
    for name,index in class_to_id.items()
}


true_labels = []
pred_labels = []

confidences = []

results = []



for plant in species:

    folder = os.path.join(
        DATASET_PATH,
        plant
    )


    for filename in os.listdir(folder):

        if not filename.lower().endswith(
            (
                ".jpg",
                ".jpeg",
                ".png"
            )
        ):
            continue


        image_path = os.path.join(
            folder,
            filename
        )


        image = Image.open(
            image_path
        ).convert(
            "RGB"
        )


        image = image.resize(
            (
                IMG_SIZE,
                IMG_SIZE
            )
        )


        image = np.array(
            image
        )


        image = image.transpose(
            2,
            0,
            1
        )


        image = np.expand_dims(
            image,
            axis=0
        )


        image = image.astype(
            np.float32
        ) / 255.0



        output = session.run(
            None,
            {
                INPUT_NAME:image
            }
        )[0]


        output = np.asarray(
            output
        )


        output = output.flatten()


        # softmax
        exp = np.exp(
            output - np.max(output)
        )


        probabilities = exp / np.sum(
            exp
        )


        prediction = int(
            np.argmax(
                probabilities
            )
        )


        confidence = float(
            np.max(
                probabilities
            )
        )


        true_id = class_to_id[plant]


        true_labels.append(
            true_id
        )


        pred_labels.append(
            prediction
        )


        confidences.append(
            confidence
        )


        results.append({

            "image": filename,

            "actual": plant,

            "prediction":
                id_to_class.get(
                    prediction,
                    "unknown"
                ),

            "confidence":
                confidence

        })



# save predictions

pd.DataFrame(
    results
).to_csv(
    f"{OUTPUT_DIR}/prediction_results.csv",
    index=False
)



# ======================================
# 9. CONFIDENCE GRAPH
# ======================================

plt.figure(
    figsize=(10,6)
)


plt.hist(
    confidences,
    bins=50
)


plt.title(
    "Prediction Confidence Distribution"
)


plt.xlabel(
    "Confidence"
)


plt.ylabel(
    "Images"
)


plt.savefig(
    f"{OUTPUT_DIR}/09_confidence_distribution.png",
    dpi=300
)


plt.close()



# ======================================
# 10. SPECIES ACCURACY
# ======================================

accuracy = accuracy_score(
    true_labels,
    pred_labels
)


matrix = confusion_matrix(
    true_labels,
    pred_labels
)



plt.figure(
    figsize=(12,10)
)


sns.heatmap(
    matrix,
    annot=True,
    fmt="d",
    xticklabels=species,
    yticklabels=species
)


plt.title(
    f"Plant Species Confusion Matrix\nAccuracy: {accuracy:.2%}"
)


plt.xlabel(
    "Predicted Species"
)


plt.ylabel(
    "Actual Species"
)


plt.tight_layout()


plt.savefig(
    f"{OUTPUT_DIR}/10_species_accuracy.png",
    dpi=300
)


plt.close()



# ======================================
# SUMMARY
# ======================================

summary = {

    "model":
        MODEL_PATH,

    "species":
        len(species),

    "images_tested":
        len(true_labels),

    "accuracy":
        float(accuracy),

    "average_confidence":
        float(np.mean(confidences)),

    "average_inference_ms":
        float(np.mean(inference_times))

}


pd.DataFrame(
    [summary]
).to_csv(
    f"{OUTPUT_DIR}/summary.csv",
    index=False
)



print()
print("==========================")
print("Analysis complete!")
print("==========================")
print(
    f"Accuracy: {accuracy:.2%}"
)
print(
    f"Average confidence: {np.mean(confidences):.2%}"
)
print(
    f"Average inference: {np.mean(inference_times):.3f} ms"
)
print()
print(
    "Results saved in:",
    OUTPUT_DIR
)