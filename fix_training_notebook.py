import json
from pathlib import Path

notebook_path = Path("Model_Training.ipynb")
notebook = json.loads(notebook_path.read_text(encoding="utf-8"))

# Find and update notebook code cells.
for cell in notebook["cells"]:
    if cell.get("cell_type") != "code":
        continue

    source = "".join(cell.get("source", []))

    # Remove Google Colab-only setup.
    source = source.replace(
        "from google.colab import drive\ndrive.mount('/content/drive')\n",
        ""
    )

    # Configure local Windows project paths.
    if "PROJECT_DIR = '/content/drive/MyDrive/Smart Retail Checkout'" in source:
        source = """from pathlib import Path

PROJECT_DIR = Path.cwd().resolve()
print("Project directory:", PROJECT_DIR)

IMG_SIZE = (224, 224)
BATCH_SIZE = 8
NUM_CLASSES = 8
EPOCHS = 15

RANDOM_SEED = 42
tf.random.set_seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)
"""

    # Apply augmentation only to training images.
    if "train_datagen = ImageDataGenerator" in source:
        source = """train_datagen = ImageDataGenerator(
    preprocessing_function=preprocess_input,
    rotation_range=12,
    width_shift_range=0.08,
    height_shift_range=0.08,
    zoom_range=0.10,
    brightness_range=(0.85, 1.15),
    horizontal_flip=False
)

val_datagen = ImageDataGenerator(preprocessing_function=preprocess_input)
test_datagen = ImageDataGenerator(preprocessing_function=preprocess_input)

training_set = train_datagen.flow_from_directory(
    str(PROJECT_DIR / 'Aug_Dataset' / 'Train'),
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    shuffle=True,
    seed=RANDOM_SEED
)

validation_set = val_datagen.flow_from_directory(
    str(PROJECT_DIR / 'Aug_Dataset' / 'Val'),
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    shuffle=False
)

testing_set = test_datagen.flow_from_directory(
    str(PROJECT_DIR / 'Aug_Dataset' / 'Test'),
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    shuffle=False
)

class_names = list(training_set.class_indices.keys())
print(f"Classes ({len(class_names)}): {class_names}")
print(f"Train: {training_set.samples} | Val: {validation_set.samples} | Test: {testing_set.samples}")

# Confirm that the notebook and backend use the same class ordering.
config_path = PROJECT_DIR / 'backend' / 'app' / 'config.py'
print("Backend config:", config_path)
"""

    # Use the absolute project-root path for saving the model.
    if "model.save_weights('custom_model.weights.h5')" in source:
        source = """weights_path = PROJECT_DIR / 'custom_model.weights.h5'
model_path = PROJECT_DIR / 'full_model.keras'

model.save_weights(str(weights_path))
model.save(str(model_path))

print("Weights saved:", weights_path)
print("Model saved:", model_path)

loaded_model = load_model(str(model_path))
print("Reload check passed.")
"""

    cell["source"] = source.splitlines(keepends=True)

# Back up the original notebook before modifying it.
backup_path = notebook_path.with_name("Model_Training.backup.ipynb")
if not backup_path.exists():
    backup_path.write_text(
        notebook_path.read_text(encoding="utf-8"),
        encoding="utf-8"
    )

notebook_path.write_text(
    json.dumps(notebook, indent=1, ensure_ascii=False) + "\n",
    encoding="utf-8"
)

print("Notebook updated successfully.")
print("Original backup:", backup_path)