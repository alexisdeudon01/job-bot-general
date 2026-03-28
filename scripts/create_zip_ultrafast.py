import os
import zipfile
from concurrent.futures import ThreadPoolExecutor

PROJECT_NAME = "job-bot-general"
ZIP_NAME = "job-bot-general_20260328.zip"
EXCLUDE_DIRS = {"venv", "__pycache__", ".git"}
EXCLUDE_FILES = {".DS_Store"}

def collect_files():
    out = []
    for root, dirs, files in os.walk(PROJECT_NAME):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file in EXCLUDE_FILES:
                continue
            full_path = os.path.join(root, file)
            out.append((full_path, os.path.relpath(full_path, start=".")))
    return out

def create_zip():
    file_list = collect_files()
    with zipfile.ZipFile(ZIP_NAME, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipf:
        for full_path, arcname in file_list:
            zipf.write(full_path, arcname)
    print(f"✅ ZIP créé : {ZIP_NAME}")

if __name__ == "__main__":
    create_zip()
