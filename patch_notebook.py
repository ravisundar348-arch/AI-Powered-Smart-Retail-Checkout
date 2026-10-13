import json
from pathlib import Path

notebook_path = Path("Model_Training.ipynb")

with notebook_path.open("r", encoding="utf-8") as file:
    notebook = json.load(file)

folder_names = [
    "Amul_ice_cream",
    "cake",
    "cerave",
    "Hns_shampoo",
    "nestley_milk_powder",
    "plum",
    "thums_up",
    "wildstone",
]

class_names = [
    "Amul_Ice_Cream",
    "Cake",
    "CeraVe",
    "HnS_Shampoo",
    "Nestle_Milk_Powder",
    "Plum",
    "Thums_Up",
    "Wild_Stone",
]

new_cell = '''train_datagen = ImageDataGenerator(
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

# Explicit folder order: must match backend model output order.
folder_names = [
    "Amul_ice_cream", "cake", "cerave", "Hns_shampoo",
    "nestley_milk_powder", "plum", "thums_up", "wildstone"
]

class_names = [
    "Amul_Ice_Cream", "Cake", "CeraVe", "HnS_Shampoo",
    "Nestle_Milk_Powder", "Plum", "Thums_Up", "Wild_Stone"
]

training_set = train_datagen.flow_from_directory(
    str(PROJECT_DIR / 'Aug_Dataset' / 'Train'),
    classes=folder_names,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    shuffle=True,
    seed=RANDOM_SEED
)

validation_set = val_datagen.flow_from_directory(
    str(PROJECT_DIR / 'Aug_Dataset' / 'Val'),
    classes=folder_names,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    shuffle=False
)

testing_set = test_datagen.flow_from_directory(
    str(PROJECT_DIR / 'Aug_Dataset' / 'Test'),
    classes=folder_names,
    target_size=IMG_SIZE,
    batch_size=BATCH_SIZE,
    class_mode='categorical',
    shuffle=False
)

assert list(training_set.class_indices.keys()) == folder_names, (
    "Training class order does not match the configured order."
)
assert list(validation_set.class_indices.keys()) == folder_names
assert list(testing_set.class_indices.keys()) == folder_names
assert len(class_names) == NUM_CLASSES

print("Backend-aligned class names:", class_names)
print("Training folder indexes:", training_set.class_indices)
print(f"Train: {training_set.samples} | Val: {validation_set.samples} | Test: {testing_set.samples}")

config_path = PROJECT_DIR / 'backend' / 'app' / 'config.py'
print("Backend config:", config_path)
'''

matches = []

for index, cell in enumerate(notebook["cells"]):
    if cell.get("cell_type") != "code":
        continue

    source = "".join(cell.get("source", []))

    if "flow_from_directory" in source and "class_names =" in source:
        matches.append(index)

if len(matches) != 1:
    raise RuntimeError(
        f"Expected exactly one data-loading cell, found {len(matches)}. "
        "Notebook was not modified."
    )

cell = notebook["cells"][matches[0]]
cell["source"] = new_cell.splitlines(keepends=True)

with notebook_path.open("w", encoding="utf-8") as file:
    json.dump(notebook, file, indent=1, ensure_ascii=False)
    file.write("\n")

print("SUCCESS: Notebook class mapping updated.")
print("Training architecture and augmentation settings preserved.")
print("Class order:", class_names)