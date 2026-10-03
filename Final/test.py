from pathlib import Path
import tkinter as tk
from tkinter import filedialog

from document_tampering import DocumentTamperingDetector


# =========================================================
# CONFIGURATION
# =========================================================

# Folder where this main.py file is located
BASE_DIR = Path(__file__).resolve().parent

# Output folder
OUTPUT_DIR = BASE_DIR / "output"

# Create output folder automatically
OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================================================
# SELECT MULTIPLE DOCUMENTS
# =========================================================

def select_documents():

    root = tk.Tk()
    root.withdraw()

    files = filedialog.askopenfilenames(
        title="Select documents for tampering analysis",

        filetypes=[
            (
                "Supported documents",
                "*.pdf *.jpg *.jpeg *.png *.bmp *.tiff *.tif"
            ),
            (
                "PDF files",
                "*.pdf"
            ),
            (
                "Image files",
                "*.jpg *.jpeg *.png *.bmp *.tiff *.tif"
            ),
            (
                "All files",
                "*.*"
            ),
        ],
    )

    root.destroy()

    return [
        Path(file)
        for file in files
    ]


# =========================================================
# PRINT SINGLE RESULT
# =========================================================

def print_result(
    document_path,
    result,
    index,
    total
):

    print("\n")
    print("=" * 80)

    print(
        f"DOCUMENT {index}/{total}"
    )

    print("=" * 80)

    print(
        f"File       : {document_path.name}"
    )

    print(
        f"Location   : {document_path}"
    )

    print(
        f"Verdict    : {result['verdict']}"
    )

    print(
        f"Risk score : {result['risk_score']}"
    )

    print(
        f"Flags      : {len(result['flags'])}"
    )

    print(
        f"Annotated  : "
        f"{', '.join(result.get('annotated_files', [])) or 'None'}"
    )

    # -----------------------------------------------------
    # FLAGS
    # -----------------------------------------------------

    if result["flags"]:

        print("\nSuspicious findings:")
        print("-" * 80)

        for number, flag in enumerate(
            result["flags"],
            start=1
        ):

            print(
                f"\n[{number}] "
                f"{flag['severity'].upper()}"
            )

            print(
                f"    Page   : "
                f"{flag['page']}"
            )

            print(
                f"    Field  : "
                f"{flag['field']}"
            )

            print(
                f"    Check  : "
                f"{flag['check']}"
            )

            print(
                f"    Reason : "
                f"{flag['reason']}"
            )

            if flag.get("bbox"):

                print(
                    f"    BBox   : "
                    f"{flag['bbox']}"
                )

    else:

        print(
            "\nNo suspicious findings detected."
        )

    print("\n" + "=" * 80)


# =========================================================
# MAIN
# =========================================================

def main():

    print("=" * 80)
    print("DOCUMENT TAMPERING DETECTION")
    print("=" * 80)

    print(
        f"\nOutput directory:\n"
        f"{OUTPUT_DIR}"
    )

    # -----------------------------------------------------
    # SELECT FILES
    # -----------------------------------------------------

    documents = select_documents()

    if not documents:

        print(
            "\nNo documents selected."
        )

        return

    print(
        f"\nSelected {len(documents)} document(s):"
    )

    for index, document in enumerate(
        documents,
        start=1
    ):

        print(
            f"  {index}. "
            f"{document.name}"
        )

    # -----------------------------------------------------
    # LOAD MODEL / DETECTOR ONCE
    # -----------------------------------------------------

    print(
        "\nInitializing document tampering detector..."
    )

    detector = DocumentTamperingDetector()

    print(
        "Detector ready."
    )

    # -----------------------------------------------------
    # ANALYZE EACH DOCUMENT
    # -----------------------------------------------------

    results = []

    for index, document in enumerate(
        documents,
        start=1
    ):

        print(
            "\n"
            + "#" * 80
        )

        print(
            f"ANALYZING "
            f"{index}/{len(documents)}"
        )

        print(
            f"File: {document.name}"
        )

        print(
            "#" * 80
        )

        try:

            result = detector.analyze(
                str(document),

                # We want annotation
                save_annotation=True,

                # JSON report can also be generated
                save_report=True,

                # We print our own formatted output
                print_output=False,
            )

            # -------------------------------------------------
            # MOVE / SAVE ANNOTATED FILES TO OUTPUT
            # -------------------------------------------------

            annotated_files = []

            for annotated_file in result.get(
                "annotated_files",
                []
            ):

                source = Path(
                    annotated_file
                )

                if not source.exists():
                    continue

                destination = (
                    OUTPUT_DIR
                    / source.name
                )

                # If annotation was already created elsewhere,
                # copy it to output/
                if source.resolve() != destination.resolve():

                    import shutil

                    shutil.copy2(
                        source,
                        destination
                    )

                annotated_files.append(
                    str(destination)
                )

            # Replace paths in result
            result[
                "annotated_files"
            ] = annotated_files

            results.append(
                result
            )

            # -------------------------------------------------
            # PRINT RESULT
            # -------------------------------------------------

            print_result(
                document,
                result,
                index,
                len(documents)
            )

        except Exception as error:

            print(
                "\nERROR:"
            )

            print(
                f"Could not analyze "
                f"{document.name}"
            )

            print(
                f"Reason: {error}"
            )

    # =====================================================
    # FINAL SUMMARY
    # =====================================================

    print("\n\n")

    print("=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)

    print(
        f"\nSelected documents : "
        f"{len(documents)}"
    )

    print(
        f"Successfully analyzed : "
        f"{len(results)}"
    )

    print(
        f"\nAnnotated images saved to:"
    )

    print(
        f"  {OUTPUT_DIR}"
    )

    print("\n")

    # -----------------------------------------------------
    # SUMMARY TABLE
    # -----------------------------------------------------

    print(
        f"{'FILE':<35}"
        f"{'VERDICT':<30}"
        f"{'RISK':<10}"
        f"{'FLAGS':<10}"
    )

    print("-" * 85)

    for result in results:

        filename = Path(
            result["file"]
        ).name

        print(
            f"{filename[:34]:<35}"
            f"{result['verdict'][:29]:<30}"
            f"{result['risk_score']:<10}"
            f"{len(result['flags']):<10}"
        )

    print("-" * 85)

    print(
        "\nAnalysis complete."
    )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":
    main()