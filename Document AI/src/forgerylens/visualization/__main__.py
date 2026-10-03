import sys
import argparse
from datetime import date
from forgerylens.pipeline import run_pipeline, STORAGE_ROOT
from forgerylens.visualization.overlay import render_evidence_overlay
from forgerylens.contracts.storage import resolve_artifact_ref

def main():
    parser = argparse.ArgumentParser(description="ForgeryLens Evidence Overlay")
    parser.add_argument("file_path", help="Path to document")
    parser.add_argument("--reference-date", help="YYYY-MM-DD", type=date.fromisoformat, default=None)
    parser.add_argument("--include-all", action="store_true", help="Include all located records")
    args = parser.parse_args()

    print(f"Running pipeline on {args.file_path}...")
    bundle = run_pipeline(args.file_path, reference_date=args.reference_date)

    print("Rendering overlay...")
    result = render_evidence_overlay(args.file_path, bundle, include_all_located=args.include_all)

    print("\nOverlay Artifacts Generated:")
    for ref in result.artifact_refs:
        local_path = resolve_artifact_ref(ref, STORAGE_ROOT)
        print(f" - {local_path}")

    if result.skipped:
        print("\nSkipped Records:")
        for s in result.skipped:
            print(f" - [{s.evidence_id}]: {s.reason}")

if __name__ == "__main__":
    main()
