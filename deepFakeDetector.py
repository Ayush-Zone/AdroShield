from pathlib import Path
import tkinter as tk
from tkinter import filedialog

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

MODEL_ID = "obuladinnesai/claim-photo-integrity-detector-v1"

TILE_SIZE = 224
OVERLAP = 0.25
BATCH_SIZE = 16
SUSPICIOUS_THRESHOLD = 0.80


def select_image():
    root = tk.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename(
        title="Select an image",
        filetypes=[
            ("Image files", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff"),
            ("JPEG files", "*.jpg *.jpeg"),
            ("PNG files", "*.png"),
            ("WebP files", "*.webp"),
            ("All files", "*.*"),
        ],
    )

    root.destroy()

    if not file_path:
        return None

    return Path(file_path)


def generate_tiles(image):
    width, height = image.size
    stride = int(TILE_SIZE * (1 - OVERLAP))

    x_positions = list(range(0, max(width - TILE_SIZE, 0) + 1, stride))
    y_positions = list(range(0, max(height - TILE_SIZE, 0) + 1, stride))

    if not x_positions or x_positions[-1] + TILE_SIZE < width:
        x_positions.append(max(width - TILE_SIZE, 0))

    if not y_positions or y_positions[-1] + TILE_SIZE < height:
        y_positions.append(max(height - TILE_SIZE, 0))

    x_positions = sorted(set(x_positions))
    y_positions = sorted(set(y_positions))

    tiles = []

    for y in y_positions:
        for x in x_positions:

            right = min(x + TILE_SIZE, width)
            bottom = min(y + TILE_SIZE, height)

            tile = image.crop((x, y, right, bottom))

            if tile.size != (TILE_SIZE, TILE_SIZE):
                padded = Image.new(
                    "RGB",
                    (TILE_SIZE, TILE_SIZE),
                    (0, 0, 0)
                )
                padded.paste(tile, (0, 0))
                tile = padded

            tiles.append({
                "image": tile,
                "x": x,
                "y": y
            })

    return tiles


def main():

    image_path = select_image()

    if image_path is None:
        print("No image selected.")
        return

    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"\nGPU: {torch.cuda.get_device_name(0)}")
    else:
        device = torch.device("cpu")
        print("\nWARNING: CUDA is not available. Using CPU.")

    image = Image.open(image_path).convert("RGB")

    print(f"\nImage: {image_path.name}")
    print(f"Original size: {image.size[0]} x {image.size[1]}")

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

    labels = list(model.config.id2label.values())

    print("\nModel classes:")

    for class_id, label in model.config.id2label.items():
        print(f"  {class_id}: {label}")

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
            f"Could not identify AI/fake label. Available labels: {labels}"
        )

    print(f"\nAI label: {ai_label}")

    print("\nCreating tiles...")

    tiles = generate_tiles(image)

    print(f"Total tiles: {len(tiles)}")

    all_results = []

    print("\nRunning inference...")

    for start in range(0, len(tiles), BATCH_SIZE):

        batch = tiles[start:start + BATCH_SIZE]

        batch_images = [
            item["image"]
            for item in batch
        ]

        inputs = processor(
            images=batch_images,
            return_tensors="pt"
        )

        inputs = {
            key: value.to(device)
            for key, value in inputs.items()
        }

        with torch.inference_mode():
            outputs = model(**inputs)

        probabilities = torch.softmax(
            outputs.logits,
            dim=-1
        )

        for index, probability in enumerate(probabilities):

            tile = batch[index]

            tile_results = {}

            for class_id, score in enumerate(probability):

                label = model.config.id2label[class_id]

                tile_results[label] = score.item()

            all_results.append({
                "x": tile["x"],
                "y": tile["y"],
                "results": tile_results
            })

        processed = min(
            start + BATCH_SIZE,
            len(tiles)
        )

        print(
            f"Processed {processed}/{len(tiles)} tiles"
        )

    tile_scores = []

    for item in all_results:

        score = item["results"].get(
            ai_label,
            0.0
        )

        tile_scores.append({
            "x": item["x"],
            "y": item["y"],
            "score": score
        })

    tile_scores.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    scores = [
        item["score"]
        for item in tile_scores
    ]

    average_ai = sum(scores) / len(scores)

    max_ai = max(scores)

    top_count = max(
        1,
        int(len(scores) * 0.10)
    )

    top_scores = scores[:top_count]

    top_10_average = (
        sum(top_scores) / len(top_scores)
    )

    suspicious_tiles = [
        item
        for item in tile_scores
        if item["score"] >= SUSPICIOUS_THRESHOLD
    ]

    print("\n" + "=" * 60)
    print("TILE FORENSIC ANALYSIS")
    print("=" * 60)

    print(f"\nTotal tiles      : {len(tile_scores)}")
    print(f"Average AI score : {average_ai:.2%}")
    print(f"Maximum AI score : {max_ai:.2%}")
    print(f"Top 10% average  : {top_10_average:.2%}")
    print(f"Suspicious tiles : {len(suspicious_tiles)}")
    print(f"Threshold        : {SUSPICIOUS_THRESHOLD:.0%}")

    print("\nTop suspicious regions:")

    for index, tile in enumerate(
        tile_scores[:10],
        start=1
    ):
        print(
            f"{index:2d}. "
            f"X={tile['x']:4d}, "
            f"Y={tile['y']:4d}, "
            f"AI={tile['score']:.2%}"
        )

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

    print("\n" + "=" * 60)
    print("PHOTO INTEGRITY RESULT")
    print("=" * 60)

    print(f"Image              : {image_path.name}")
    print(
        f"Original size      : "
        f"{image.size[0]} x {image.size[1]}"
    )
    print(f"Average AI score   : {average_ai:.2%}")
    print(f"Maximum AI score   : {max_ai:.2%}")
    print(f"Top 10% average    : {top_10_average:.2%}")
    print(f"Suspicious regions : {len(suspicious_tiles)}")
    print(f"Decision            : {decision}")

    print("=" * 60)


if __name__ == "__main__":
    main()