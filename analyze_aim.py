from pathlib import Path
import math
import sys

from awpy import Demo
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill


demo_path = Path("demos/sample.dem")
if not demo_path.exists():
    raise FileNotFoundError(f"Demo not found: {demo_path.resolve()}")

output_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports")
output_folder.mkdir(parents=True, exist_ok=True)

demo = Demo(str(demo_path))
demo.load("shots")
shots = demo.shots.sort(["steamid", "tick"])

previous = {}
results = []


def angle_difference(current, old):
    """Return the smallest signed difference between two angles."""
    return (current - old + 180) % 360 - 180


for row in shots.iter_rows(named=True):
    steamid = row["steamid"]
    name = row["name"] or "Unknown"
    tick = row["tick"]
    pitch = row["pitch"]
    yaw = row["yaw"]

    if steamid is None or pitch is None or yaw is None or tick is None:
        continue
    if not (math.isfinite(float(pitch)) and math.isfinite(float(yaw))):
        continue

    key = str(steamid)
    if key in previous:
        old = previous[key]
        tick_gap = tick - old["tick"]
        if tick_gap > 0:
            pitch_change = float(pitch) - old["pitch"]
            yaw_change = angle_difference(float(yaw), old["yaw"])
            angle_change = math.sqrt(pitch_change ** 2 + yaw_change ** 2)
            results.append({
                "Steam ID": key,
                "Player": name,
                "Previous Tick": old["tick"],
                "Current Tick": tick,
                "Tick Gap": tick_gap,
                "Pitch Change (degrees)": round(pitch_change, 3),
                "Yaw Change (degrees)": round(yaw_change, 3),
                "Combined Angle Change (degrees)": round(angle_change, 3),
            })

    previous[key] = {"tick": tick, "pitch": float(pitch), "yaw": float(yaw)}

headers = [
    "Steam ID", "Player", "Previous Tick", "Current Tick", "Tick Gap",
    "Pitch Change (degrees)", "Yaw Change (degrees)",
    "Combined Angle Change (degrees)",
]

workbook = Workbook()
sheet = workbook.active
sheet.title = "Aim Changes"
sheet.append(headers)
for result in results:
    sheet.append([result[h] for h in headers])

sheet.freeze_panes = "A2"
sheet.auto_filter.ref = sheet.dimensions
for cell in sheet[1]:
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill(fill_type="solid", fgColor="1F4E78")
for column in sheet.columns:
    letter = column[0].column_letter
    max_length = max((len(str(cell.value or "")) for cell in column), default=0)
    sheet.column_dimensions[letter].width = min(max_length + 2, 38)

output_file = output_folder / "aim_angle_analysis.xlsx"
workbook.save(output_file)

print("Aim analysis complete!")
print(f"Valid consecutive event comparisons: {len(results)}")
print(f"Saved to: {output_file.resolve()}")
if not results:
    print("No consecutive shot events with valid angles were found.")
