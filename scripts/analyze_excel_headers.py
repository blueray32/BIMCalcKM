import sys
import pandas as pd
import os

def analyze_file(file_path):
    print(f"\n--- Analyzing: {file_path} ---")
    if not os.path.exists(file_path):
        print("File not found.")
        return

    try:
        # Read the first few rows to infer headers
        df = pd.read_excel(file_path, nrows=5)
        print("Columns:", list(df.columns))
        print("\nFirst 3 rows:")
        print(df.head(3).to_string())
        
        # Basic stats
        print(f"\nShape: {df.shape}")
        
    except Exception as e:
        print(f"Error reading file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_excel_headers.py <file_path> ...")
        sys.exit(1)

    for path in sys.argv[1:]:
        analyze_file(path)
