import tkinter as tk
from tkinter import filedialog

from photo_integrity import PhotoIntegrityDetector


def select_images():
    """Open a file dialog allowing multiple image selection."""

    root = tk.Tk()
    root.withdraw()

    file_paths = filedialog.askopenfilenames(
        title="Select images for integrity analysis",
        filetypes=[
            (
                "Image files",
                "*.jpg *.jpeg *.png *.webp *.bmp *.tiff"
            ),
            ("JPEG files", "*.jpg *.jpeg"),
            ("PNG files", "*.png"),
            ("WebP files", "*.webp"),
            ("BMP files", "*.bmp"),
            ("TIFF files", "*.tiff"),
            ("All files", "*.*"),
        ],
    )

    root.destroy()

    return file_paths


def main():

    # ---------------------------------------------------------
    # SELECT MULTIPLE IMAGES
    # ---------------------------------------------------------

    image_paths = select_images()

    if not image_paths:
        print("No images selected.")
        return

    print("\n" + "=" * 70)
    print("PHOTO INTEGRITY ANALYZER")
    print("=" * 70)

    print(f"\nSelected images: {len(image_paths)}")

    for index, path in enumerate(image_paths, start=1):
        print(f"{index}. {path}")

    # ---------------------------------------------------------
    # LOAD MODEL ONCE
    # ---------------------------------------------------------

    print("\nLoading AI model...")

    detector = PhotoIntegrityDetector()

    print("Model ready.")

    # Store all results
    results = []

    # ---------------------------------------------------------
    # ANALYZE IMAGES
    # ---------------------------------------------------------

    for index, image_path in enumerate(
        image_paths,
        start=1
    ):

        print("\n")
        print("=" * 70)
        print(
            f"IMAGE {index}/{len(image_paths)}"
        )
        print("=" * 70)

        print(f"File: {image_path}")

        try:

            result = detector.analyze(
                image_path
            )

            results.append(result)

            # -------------------------------------------------
            # RESULT
            # -------------------------------------------------

            print("\nDecision:")
            print(
                f"  {result['decision']}"
            )

            print("\nScores:")

            print(
                f"  Average AI score : "
                f"{result['average_ai_score']:.2%}"
            )

            print(
                f"  Maximum AI score : "
                f"{result['maximum_ai_score']:.2%}"
            )

            print(
                f"  Top 10% average  : "
                f"{result['top_10_average']:.2%}"
            )

            print(
                f"  Suspicious tiles : "
                f"{result['suspicious_tile_count']}"
            )

            # -------------------------------------------------
            # TOP SUSPICIOUS REGIONS
            # -------------------------------------------------

            print(
                "\nTop suspicious regions:"
            )

            for region in result[
                "top_suspicious_regions"
            ]:

                print(
                    f"  X={region['x']:4d}, "
                    f"Y={region['y']:4d}, "
                    f"AI={region['score']:.2%}"
                )

        except Exception as e:

            print(
                f"\nERROR analyzing "
                f"{image_path}:"
            )

            print(e)

    # ---------------------------------------------------------
    # FINAL SUMMARY
    # ---------------------------------------------------------

    print("\n\n")
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)

    print(
        f"\nImages selected : "
        f"{len(image_paths)}"
    )

    print(
        f"Images analyzed : "
        f"{len(results)}"
    )

    print("\n")

    for index, result in enumerate(
        results,
        start=1
    ):

        print(
            f"{index:2d}. "
            f"{result['filename']}"
        )

        print(
            f"    Decision       : "
            f"{result['decision']}"
        )

        print(
            f"    Average AI     : "
            f"{result['average_ai_score']:.2%}"
        )

        print(
            f"    Maximum AI     : "
            f"{result['maximum_ai_score']:.2%}"
        )

        print(
            f"    Suspicious     : "
            f"{result['suspicious_tile_count']} tiles"
        )

        print()


if __name__ == "__main__":
    main()