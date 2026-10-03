import sys
import os
import json

# Ensure the src module can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.matcher import verify_identity

def main():
    print("==================================================")
    print("      === ADROSHIELD Identity AI: Live Demo ===")
    print("==================================================\n")
    
    try:
        id_path = input("Enter path to ID Document: ").strip().strip('"').strip("'")
        selfie_path = input("Enter path to Selfie Image: ").strip().strip('"').strip("'")
    except KeyboardInterrupt:
        print("\nDemo aborted by user.")
        sys.exit(0)
        
    if not id_path or not selfie_path:
        print("Error: Both paths are required.")
        sys.exit(1)
        
    print(f"\nAnalyzing ID: {id_path}")
    print(f"Analyzing Selfie: {selfie_path}")
    print("Running AI Pipeline...\n")
    
    # Run the verification
    result = verify_identity(id_path, selfie_path)
    
    print(json.dumps(result, indent=4))

if __name__ == "__main__":
    main()
