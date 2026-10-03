import sys
import json
from forgerylens.pipeline import run_pipeline
from forgerylens.demo_hook import generate_demo_ui_payload

def main():
    if len(sys.argv) < 2:
        print("Usage: python demo_runner.py <path_to_document>")
        sys.exit(1)
        
    doc_path = sys.argv[1]
    print(f"Running ForgeryLens Pipeline on: {doc_path}")
    
    # Run the pipeline
    try:
        bundle = run_pipeline(doc_path)
    except Exception as e:
        print(f"Pipeline error: {e}")
        sys.exit(1)
        
    # Translate to UI Demo format
    ui_payload = generate_demo_ui_payload(bundle)
    
    # Print it out nicely
    print("\n--- FORGERYLENS UI DEMO PAYLOAD ---")
    print(json.dumps(ui_payload, indent=2))
    print("-----------------------------------\n")

if __name__ == "__main__":
    main()
