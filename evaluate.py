import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    accuracy_score, 
    precision_recall_fscore_support,
    roc_curve,
    auc
)

# =====================================================================
# 1. SIMULATE OR LOAD YOUR TEST DATA
# =====================================================================
# NOTE: Replace this section with code that loads your real test images 
# and runs them through your model to get actual vs. predicted labels.

# Define your plant classes
classes = ['Healthy Plant', 'Broadleaf Weed', 'Grassy Weed', 'Sedge']

# Example simulated test data (replace with your actual model outputs):
np.random.seed(42)
y_true = np.random.choice(classes, size=150, p=[0.4, 0.3, 0.2, 0.1])
# Simulating predictions with ~80% accuracy
y_pred = [
    val if np.random.rand() < 0.8 else np.random.choice(classes) 
    for val in y_true
]

# =====================================================================
# 2. CALCULATE CORE METRICS
# =====================================================================
accuracy = accuracy_score(y_true, y_pred)
precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='weighted')

print("=" * 60)
print("                    AI ENGINE PERFORMANCE REPORT             ")
print("=" * 60)
print(f"Overall Accuracy : {accuracy:.4f} ({accuracy * 100:.2f}%)")
print(f"Weighted Precision: {precision:.4f}")
print(f"Weighted Recall   : {recall:.4f}")
print(f"Weighted F1-Score : {f1:.4f}")
print("-" * 60)

# Detailed per-class precision, recall, and f1-score
class_report = classification_report(y_true, y_pred, target_names=classes)
print("Detailed Class Analysis:")
print(class_report)
print("=" * 60)

# =====================================================================
# 3. GENERATE & SAVE PLOTS
# =====================================================================
os.makedirs('metrics_output', exist_ok=True)
sns.set_theme(style="darkgrid")

# --- Plot 1: Confusion Matrix ---
plt.figure(figsize=(8, 6))
cm = confusion_matrix(y_true, y_pred, labels=classes)
sns.heatmap(
    cm, 
    annot=True, 
    fmt='d', 
    cmap='Greens', 
    xticklabels=classes, 
    yticklabels=classes,
    cbar=False,
    annot_kws={"size": 14, "weight": "bold"}
)
plt.title('Sprout AI - Confusion Matrix', fontsize=16, pad=20, weight='bold')
plt.ylabel('Actual Label', fontsize=12, labelpad=10)
plt.xlabel('Predicted Label', fontsize=12, labelpad=10)
plt.tight_layout()
plt.savefig('metrics_output/confusion_matrix.png', dpi=300)
plt.close()

# --- Plot 2: Per-Class Performance Bar Chart ---
precision_per_class, recall_per_class, f1_per_class, _ = precision_recall_fscore_support(
    y_true, y_pred, labels=classes
)

metrics_df = pd.DataFrame({
    'Class': classes * 3,
    'Score': np.concatenate([precision_per_class, recall_per_class, f1_per_class]),
    'Metric': ['Precision'] * len(classes) + ['Recall'] * len(classes) + ['F1-Score'] * len(classes)
})

plt.figure(figsize=(10, 6))
sns.barplot(x='Class', y='Score', hue='Metric', data=metrics_df, palette='viridis')
plt.title('AI Engine Diagnostics per Plant Type', fontsize=16, pad=20, weight='bold')
plt.ylim(0, 1.1)
plt.ylabel('Score (0.0 - 1.0)', fontsize=12)
plt.xlabel('Plant Classification Category', fontsize=12)
plt.legend(loc='lower right', frameon=True)
plt.tight_layout()
plt.savefig('metrics_output/class_performance.png', dpi=300)
plt.close()

print("[Success] Metric graphs saved successfully to the 'metrics_output/' directory:")
print("  - metrics_output/confusion_matrix.png")
print("  - metrics_output/class_performance.png")
print("=" * 60)