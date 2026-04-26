import zipfile
import os

zip_filename = "office_handoff_package.zip"
include_dirs = ["app", "prompts", "config", "scripts", "tests"]
include_files = [".env.example", "requirements.txt", "pyproject.toml"]

# Get artifact paths
artifacts_dir = r"C:\Users\doors\.gemini\antigravity\brain\eaacb8aa-c5ce-4caf-9ea8-47f97d4c060c"
artifact_files = [
    "walkthrough.md",
    "CURRENT_STATUS.md",
    "NEXT_STEPS.md",
    "CHANGED_FILES.md",
    "TEST_COMMANDS.md",
    "SECURITY_CHECK.md"
]

exclude_dirs = [".venv", "venv", "__pycache__", ".pytest_cache", ".chroma"]

def should_exclude(path):
    parts = path.split(os.sep)
    for ed in exclude_dirs:
        if ed in parts:
            return True
    if path.endswith(".jsonl"):
        return True
    if "ChromaDB" in parts:
        return True
    if "logs" in parts:
        return True
    # Exclude any actual .env just in case it was explicitly added somehow, though we only add explicitly via dirs
    if path.endswith(".env"):
        return True
    return False

with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for d in include_dirs:
        if os.path.exists(d):
            for root, dirs, files in os.walk(d):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not should_exclude(file_path):
                        zipf.write(file_path, os.path.relpath(file_path, "."))

    for f in include_files:
        if os.path.exists(f):
            zipf.write(f, f)

    for f in artifact_files:
        path = os.path.join(artifacts_dir, f)
        if os.path.exists(path):
            zipf.write(path, f)

print(f"Created {zip_filename}")
