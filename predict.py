from pathlib import Path

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification


# ============================================================
# CONFIGURATION
# ============================================================

MODEL_ID = "obuladinnesai/claim-photo-integrity-detector-v1"

BASE_DIR = Path(__file__).resolve().parent

REAL_FOLDER = BASE_DIR / "test_images" / "real"
FAKE_FOLDER = BASE_DIR / "test_images" / "Fake"

TILE_SIZE = 224
OVERLAP = 0.25
BATCH_SIZE = 16

SUSPICIOUS_THRESHOLD = 0.80

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tiff",
}


# ============================================================
# DEVICE
# ============================================================

if torch.cuda.is_available():
    device = torch.device("cuda")
    print(f"\nGPU: {torch.cuda.get_device_name(0)}")
else:
    device = torch.device("cpu")
    print("\nWARNING: CUDA unavailable. Using CPU.")


# ============================================================
# LOAD MODEL ONCE
# ============================================================

print("\nLoading image processor...")

processor = AutoImageProcessor.from_pretrained(
    MODEL_ID
)

print("Loading model...")

model = AutoModelForImageClassification.from_pretrained(
    MODEL_ID
)

model = model.to(device)
model.eval()


# ============================================================
# FIND AI / FAKE CLASS
# ============================================================

print("\nModel classes:")

for class_id, label in model.config.id2label.items():
    print(f"  {class_id}: {label}")

labels = list(model.config.id2label.values())

ai_label = None

for label in labels:

    label_lower = label.lower()

    if (
        "ai" in label_lower
        or "fake" in label_lower
        or "synthetic" in label_lower
    ):
        ai_label = label
        break

if ai_label is None:
    raise RuntimeError(
        "Could not identify AI/fake label. "
        f"Available labels: {labels}"
    )

print(f"\nAI label: {ai_label}")


# ============================================================
# GENERATE OVERLAPPING TILES
# ============================================================

def generate_tiles(image):

    width, height = image.size

    stride = int(
        TILE_SIZE * (1 - OVERLAP)
    )

    x_positions = list(
        range(
            0,
            max(width - TILE_SIZE, 0) + 1,
            stride,
        )
    )

    y_positions = list(
        range(
            0,
            max(height - TILE_SIZE, 0) + 1,
            stride,
        )
    )

    if (
        not x_positions
        or x_positions[-1] + TILE_SIZE < width
    ):
        x_positions.append(
            max(width - TILE_SIZE, 0)
        )

    if (
        not y_positions
        or y_positions[-1] + TILE_SIZE < height
    ):
        y_positions.append(
            max(height - TILE_SIZE, 0)
        )

    x_positions = sorted(set(x_positions))
    y_positions = sorted(set(y_positions))

    tiles = []

    for y in y_positions:

        for x in x_positions:

            right = min(
                x + TILE_SIZE,
                width
            )

            bottom = min(
                y + TILE_SIZE,
                height
            )

            tile = image.crop(
                (x, y, right, bottom)
            )

            if tile.size != (
                TILE_SIZE,
                TILE_SIZE,
            ):

                padded = Image.new(
                    "RGB",
                    (TILE_SIZE, TILE_SIZE),
                    (0, 0, 0),
                )

                padded.paste(
                    tile,
                    (0, 0),
                )

                tile = padded

            tiles.append({
                "image": tile,
                "x": x,
                "y": y,
            })

    return tiles


# ============================================================
# ANALYZE ONE IMAGE
# ============================================================

def analyze_image(image_path):

    image = Image.open(
        image_path
    ).convert("RGB")

    tiles = generate_tiles(image)

    tile_scores = []

    # --------------------------------------------
    # Process tiles in batches
    # --------------------------------------------

    for start in range(
        0,
        len(tiles),
        BATCH_SIZE,
    ):

        batch = tiles[
            start:start + BATCH_SIZE
        ]

        batch_images = [
            item["image"]
            for item in batch
        ]

        inputs = processor(
            images=batch_images,
            return_tensors="pt",
        )

        inputs = {
            key: value.to(device)
            for key, value
            in inputs.items()
        }

        with torch.inference_mode():

            outputs = model(
                **inputs
            )

        probabilities = torch.softmax(
            outputs.logits,
            dim=-1,
        )

        for index, probability in enumerate(
            probabilities
        ):

            tile = batch[index]

            ai_score = 0.0

            for class_id, score in enumerate(
                probability
            ):

                label = (
                    model.config
                    .id2label[class_id]
                )

                if label == ai_label:
                    ai_score = score.item()
                    break

            tile_scores.append({
                "x": tile["x"],
                "y": tile["y"],
                "score": ai_score,
            })

    # --------------------------------------------
    # Sort suspicious areas
    # --------------------------------------------

    tile_scores.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    scores = [
        item["score"]
        for item in tile_scores
    ]

    average_ai = (
        sum(scores) / len(scores)
    )

    max_ai = max(scores)

    top_count = max(
        1,
        int(len(scores) * 0.10),
    )

    top_scores = scores[:top_count]

    top_10_average = (
        sum(top_scores)
        / len(top_scores)
    )

    suspicious_tiles = [
        item
        for item in tile_scores
        if item["score"]
        >= SUSPICIOUS_THRESHOLD
    ]

    # ========================================================
    # DECISION
    # ========================================================

    if (
        max_ai >= 0.95
        and len(suspicious_tiles) >= 1
    ):

        decision = "MANIPULATION SUSPECTED"

    elif top_10_average >= 0.75:

        decision = "MANIPULATION SUSPECTED"

    elif average_ai >= 0.50:

        decision = "REVIEW"

    else:

        decision = "LIKELY REAL"

    return {
        "image": image_path.name,
        "width": image.size[0],
        "height": image.size[1],
        "tiles": len(tile_scores),
        "average_ai": average_ai,
        "max_ai": max_ai,
        "top_10_average": top_10_average,
        "suspicious_tiles": len(
            suspicious_tiles
        ),
        "decision": decision,
    }


# ============================================================
# GET DATASET IMAGES
# ============================================================

def get_images(folder):

    if not folder.exists():

        print(
            f"\nFolder not found: {folder}"
        )

        return []

    return sorted([
        file
        for file in folder.iterdir()
        if (
            file.is_file()
            and file.suffix.lower()
            in SUPPORTED_EXTENSIONS
        )
    ])


# ============================================================
# TEST DATASET
# ============================================================

def test_dataset(
    folder,
    expected_type,
):

    images = get_images(folder)

    total = len(images)

    correct = 0
    wrong = 0
    review = 0

    print()
    print("=" * 75)
    print(
        f"TESTING {expected_type} DATASET"
    )
    print("=" * 75)

    print(
        f"Images found: {total}"
    )

    for index, image_path in enumerate(
        images,
        start=1,
    ):

        print()
        print(
            f"[{index}/{total}] "
            f"{image_path.name}"
        )

        try:

            result = analyze_image(
                image_path
            )

            decision = result["decision"]

            # ------------------------------------
            # Determine correctness
            # ------------------------------------

            if expected_type == "REAL":

                is_correct = (
                    decision == "LIKELY REAL"
                )

            else:

                is_correct = (
                    decision
                    == "MANIPULATION SUSPECTED"
                )

            if decision == "REVIEW":

                review += 1
                status = "REVIEW"

            elif is_correct:

                correct += 1
                status = "CORRECT"

            else:

                wrong += 1
                status = "WRONG"

            print(
                f"Tiles          : "
                f"{result['tiles']}"
            )

            print(
                f"Average AI     : "
                f"{result['average_ai']:.2%}"
            )

            print(
                f"Maximum AI     : "
                f"{result['max_ai']:.2%}"
            )

            print(
                f"Top 10% AI     : "
                f"{result['top_10_average']:.2%}"
            )

            print(
                f"Suspicious     : "
                f"{result['suspicious_tiles']}"
            )

            print(
                f"Decision       : "
                f"{decision}"
            )

            print(
                f"Result         : "
                f"{status}"
            )

        except Exception as error:

            wrong += 1

            print(
                f"ERROR: {error}"
            )

    # --------------------------------------------------------
    # Dataset accuracy
    # --------------------------------------------------------

    accuracy = (
        (correct / total) * 100
        if total > 0
        else 0
    )

    return {
        "total": total,
        "correct": correct,
        "wrong": wrong,
        "review": review,
        "accuracy": accuracy,
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 75)
    print("CLAIM PHOTO INTEGRITY DETECTOR")
    print("=" * 75)

    print(f"Device : {device}")
    print(f"Model  : {MODEL_ID}")

    # --------------------------------------------------------
    # REAL dataset
    # --------------------------------------------------------

    real_results = test_dataset(
        REAL_FOLDER,
        "REAL",
    )

    # --------------------------------------------------------
    # FAKE dataset
    # --------------------------------------------------------

    fake_results = test_dataset(
        FAKE_FOLDER,
        "FAKE",
    )

    # --------------------------------------------------------
    # Overall statistics
    # --------------------------------------------------------

    total = (
        real_results["total"]
        + fake_results["total"]
    )

    correct = (
        real_results["correct"]
        + fake_results["correct"]
    )

    wrong = (
        real_results["wrong"]
        + fake_results["wrong"]
    )

    review = (
        real_results["review"]
        + fake_results["review"]
    )

    overall_accuracy = (
        (correct / total) * 100
        if total > 0
        else 0
    )

    # ========================================================
    # FINAL COMPARISON
    # ========================================================

    print()
    print()
    print("=" * 75)
    print("FINAL DATASET COMPARISON")
    print("=" * 75)

    print()
    print("REAL IMAGES")
    print("-" * 35)

    print(
        f"Total       : "
        f"{real_results['total']}"
    )

    print(
        f"Correct     : "
        f"{real_results['correct']}"
    )

    print(
        f"Wrong       : "
        f"{real_results['wrong']}"
    )

    print(
        f"Review      : "
        f"{real_results['review']}"
    )

    print(
        f"Accuracy    : "
        f"{real_results['accuracy']:.2f}%"
    )

    print()
    print("FAKE / MANIPULATED IMAGES")
    print("-" * 35)

    print(
        f"Total       : "
        f"{fake_results['total']}"
    )

    print(
        f"Correct     : "
        f"{fake_results['correct']}"
    )

    print(
        f"Wrong       : "
        f"{fake_results['wrong']}"
    )

    print(
        f"Review      : "
        f"{fake_results['review']}"
    )

    print(
        f"Accuracy    : "
        f"{fake_results['accuracy']:.2f}%"
    )

    print()
    print("OVERALL")
    print("-" * 35)

    print(
        f"Total       : {total}"
    )

    print(
        f"Correct     : {correct}"
    )

    print(
        f"Wrong       : {wrong}"
    )

    print(
        f"Review      : {review}"
    )

    print(
        f"Accuracy    : "
        f"{overall_accuracy:.2f}%"
    )

    print()
    print("=" * 75)


if __name__ == "__main__":
    main()