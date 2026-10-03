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
    
    while True:
        try:
            id_path = input("Enter path to ID Document: ").strip().strip('"').strip("'")
            selfie_path = input("Enter path to Selfie Image: ").strip().strip('"').strip("'")
        except KeyboardInterrupt:
            print("\nDemo aborted by user.")
            sys.exit(0)
            
        if not id_path or not selfie_path:
            print("Error: Both paths are required.")
            continue
            
        print(f"\nAnalyzing ID: {id_path}")
        print(f"Analyzing Selfie: {selfie_path}")
        print("Running AI Pipeline...\n")
        
        try:
            # Run the verification
            result = verify_identity(id_path, selfie_path)
            print(json.dumps(result, indent=4))
        except Exception as e:
            print("\n[!] FATAL ERROR during verification pipeline:")
            print(str(e))
            
        try:
            again = input("\nEvaluate another claim? (y/n): ").strip().lower()
            if again == 'n':
                break
        except KeyboardInterrupt:
            print("\nDemo aborted by user.")
            break

if __name__ == "__main__":
    main()
