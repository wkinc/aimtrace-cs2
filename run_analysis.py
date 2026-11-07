from pathlib import Path
from datetime import datetime
import subprocess
import sys
import re


PROJECT_FOLDER = Path(__file__).resolve().parent
DEMO_PATH = PROJECT_FOLDER / "demos" / "sample.dem"

if not DEMO_PATH.exists():
    raise FileNotFoundError(f"Demo not found: {DEMO_PATH}")

timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
safe_demo_name = re.sub(r"[^A-Za-z0-9_-]", "_", DEMO_PATH.stem)
output_folder = PROJECT_FOLDER / "reports" / f"{timestamp}_{safe_demo_name}"
output_folder.mkdir(parents=True, exist_ok=True)

scripts = [
    "export_demo.py",
    "analyze_demo.py",
    "analyze_aim.py",
    "review_aim.py",
    "analyze_movement.py",
]

print(f"\nDemo: {DEMO_PATH.name}")
print(f"All reports will be saved in:\n{output_folder}\n")

for script in scripts:
    script_path = PROJECT_FOLDER / script
    print(f"\n--- Running {script} ---")
    result = subprocess.run(
        [sys.executable, str(script_path), str(output_folder)],
        cwd=PROJECT_FOLDER,
    )
    if result.returncode != 0:
        raise SystemExit(f"{script} failed with exit code {result.returncode}")

print("\nAll analysis steps completed.")
print(f"Reports folder: {output_folder}")
print("Start the dashboard with: python -m streamlit run app.py")
