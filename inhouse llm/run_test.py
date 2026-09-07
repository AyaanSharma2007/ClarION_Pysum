import sys
import os

# Append the current directory so that modules are found
sys.path.append(os.getcwd())

from pipeline import run_bootstrap

if __name__ == "__main__":
    print("Running bootstrap pipeline with Qwen 2.5 3B...")
    try:
        run_bootstrap(data_dir=".", db_string=None)
    except Exception as e:
        print(f"Error during execution: {e}")
