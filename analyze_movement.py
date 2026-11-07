from pathlib import Path
import math
import sys

from awpy import Demo
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


# Settings
DEMO_PATH = Path("demos/sample.dem")
SAMPLE_EVERY_TICKS = 4
MAX_COMPARISON_GAP_TICKS = 8
REVIEW_ANGLE_CHANGE_DEGREES = 20.0


def angle_difference(current, old):
    """Smallest signed angle difference, handling the -180/180 boundary."""
    return (current - old + 180.0) % 360.0 - 180.0


def style_sheet(sheet):
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center")
    for column in sheet.columns:
        letter = column[0].column_letter
        max_length = max((len(str(cell.value or "")) for cell in column), default=0)
        sheet.column_dimensions[letter].width = min(max_length + 2, 38)


if not DEMO_PATH.exists():
    raise FileNotFoundError(f"Demo not found: {DEMO_PATH.resolve()}")

# The runner passes the common timestamped output folder as its first argument.
output_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports")
output_folder.mkdir(parents=True, exist_ok=True)

print(f"Loading demo: {DEMO_PATH.resolve()}")
print(f"Sampling every {SAMPLE_EVERY_TICKS} ticks. This may take a while for a full match.")

demo = Demo(str(DEMO_PATH))
snapshots = demo.snapshots(every=SAMPLE_EVERY_TICKS)

if snapshots.is_empty():
    raise RuntimeError(
        "Awpy returned no player snapshots. Check that this is a valid CS2 demo."
    )

required_columns = {"tick", "steamid", "name", "pitch", "yaw"}
missing_columns = required_columns - set(snapshots.columns)
if missing_columns:
    raise RuntimeError(
        f"Snapshot data is missing columns: {sorted(missing_columns)}. "
        f"Available columns: {snapshots.columns}"
    )

# Keep only fields useful for this first movement-analysis version.
optional_columns = ["round_num", "side", "x", "y", "z", "health"]
keep_columns = ["tick", "steamid", "name", "pitch", "yaw"]
keep_columns += [col for col in optional_columns if col in snapshots.columns]
snapshots = snapshots.select(keep_columns).sort(["steamid", "tick"])

tick_rate = float(demo.tick_rate or 64.0)
previous = {}
sample_rows = []
candidate_rows = []

for row in snapshots.iter_rows(named=True):
    steamid = row["steamid"]
    tick = row["tick"]
    pitch = row["pitch"]
    yaw = row["yaw"]

    if steamid is None or tick is None or pitch is None or yaw is None:
        continue

    pitch = float(pitch)
    yaw = float(yaw)
    if not (math.isfinite(pitch) and math.isfinite(yaw)):
        continue

    name = row.get("name") or "Unknown"
    key = str(steamid)
    round_num = row.get("round_num")
    old = previous.get(key)

    tick_gap = None
    pitch_change = None
    yaw_change = None
    angle_change = None
    seconds_gap = None
    degrees_per_second = None
    position_change = None

    # Avoid comparing across rounds or large gaps, such as death/spectator gaps.
    same_round = (
        old is not None
        and (round_num is None or old["round_num"] is None or round_num == old["round_num"])
    )

    if same_round:
        tick_gap = int(tick) - old["tick"]
        if 0 < tick_gap <= MAX_COMPARISON_GAP_TICKS:
            pitch_change = pitch - old["pitch"]
            yaw_change = angle_difference(yaw, old["yaw"])
            angle_change = math.sqrt(pitch_change ** 2 + yaw_change ** 2)
            seconds_gap = tick_gap / tick_rate
            degrees_per_second = angle_change / seconds_gap if seconds_gap > 0 else None

            if all(row.get(k) is not None for k in ("x", "y", "z")) and all(
                old.get(k) is not None for k in ("x", "y", "z")
            ):
                position_change = math.sqrt(
                    (float(row["x"]) - old["x"]) ** 2
                    + (float(row["y"]) - old["y"]) ** 2
                    + (float(row["z"]) - old["z"]) ** 2
                )

    sample = {
        "Tick": int(tick),
        "Time (seconds)": round(int(tick) / tick_rate, 3),
        "Round": round_num,
        "Steam ID": key,
        "Player": name,
        "Side": row.get("side"),
        "X": row.get("x"),
        "Y": row.get("y"),
        "Z": row.get("z"),
        "Pitch": round(pitch, 3),
        "Yaw": round(yaw, 3),
        "Tick Gap": tick_gap,
        "Pitch Change (degrees)": round(pitch_change, 3) if pitch_change is not None else None,
        "Yaw Change (degrees)": round(yaw_change, 3) if yaw_change is not None else None,
        "Aim Change (degrees)": round(angle_change, 3) if angle_change is not None else None,
        "Aim Speed (degrees/second)": round(degrees_per_second, 3) if degrees_per_second is not None else None,
        "Position Change (units)": round(position_change, 3) if position_change is not None else None,
    }
    sample_rows.append(sample)

    if (
        angle_change is not None
        and tick_gap is not None
        and tick_gap <= MAX_COMPARISON_GAP_TICKS
        and angle_change >= REVIEW_ANGLE_CHANGE_DEGREES
    ):
        candidate_rows.append({
            "Tick": int(tick),
            "Time (seconds)": round(int(tick) / tick_rate, 3),
            "Round": round_num,
            "Steam ID": key,
            "Player": name,
            "Tick Gap": tick_gap,
            "Aim Change (degrees)": round(angle_change, 3),
            "Aim Speed (degrees/second)": round(degrees_per_second, 3),
            "Pitch Change (degrees)": round(pitch_change, 3),
            "Yaw Change (degrees)": round(yaw_change, 3),
            "Review Note": "Large sampled view-angle change; manually inspect demo",
        })

    previous[key] = {
        "tick": int(tick),
        "round_num": round_num,
        "pitch": pitch,
        "yaw": yaw,
        "x": float(row["x"]) if row.get("x") is not None else None,
        "y": float(row["y"]) if row.get("y") is not None else None,
        "z": float(row["z"]) if row.get("z") is not None else None,
    }

sample_headers = list(sample_rows[0].keys()) if sample_rows else [
    "Tick", "Time (seconds)", "Round", "Steam ID", "Player", "Side", "X", "Y", "Z",
    "Pitch", "Yaw", "Tick Gap", "Pitch Change (degrees)", "Yaw Change (degrees)",
    "Aim Change (degrees)", "Aim Speed (degrees/second)", "Position Change (units)"
]
candidate_headers = [
    "Tick", "Time (seconds)", "Round", "Steam ID", "Player", "Tick Gap",
    "Aim Change (degrees)", "Aim Speed (degrees/second)",
    "Pitch Change (degrees)", "Yaw Change (degrees)", "Review Note",
]

workbook = Workbook()
samples_sheet = workbook.active
samples_sheet.title = "Movement Samples"
samples_sheet.append(sample_headers)
for item in sample_rows:
    samples_sheet.append([item.get(header) for header in sample_headers])
style_sheet(samples_sheet)

candidate_sheet = workbook.create_sheet("Review Candidates")
candidate_sheet.append(candidate_headers)
for item in candidate_rows:
    candidate_sheet.append([item.get(header) for header in candidate_headers])
style_sheet(candidate_sheet)

info_sheet = workbook.create_sheet("Settings")
info_sheet.append(["Setting", "Value"])
info_sheet.append(["Demo", str(DEMO_PATH)])
info_sheet.append(["Tick rate", tick_rate])
info_sheet.append(["Sampling every ticks", SAMPLE_EVERY_TICKS])
info_sheet.append(["Maximum comparison gap (ticks)", MAX_COMPARISON_GAP_TICKS])
info_sheet.append(["Review candidate angle threshold (degrees)", REVIEW_ANGLE_CHANGE_DEGREES])
info_sheet.append(["Sample rows", len(sample_rows)])
info_sheet.append(["Review candidates", len(candidate_rows)])
info_sheet.append(["Caution", "Candidates are not proof of cheating; inspect the demo manually."])
style_sheet(info_sheet)

output_file = output_folder / "aim_movement_analysis.xlsx"
workbook.save(output_file)

print("\nAim movement analysis complete!")
print(f"Tick rate: {tick_rate}")
print(f"Movement samples exported: {len(sample_rows)}")
print(f"Review candidates: {len(candidate_rows)}")
print(f"Saved to: {output_file.resolve()}")
print("Large view-angle changes can be normal flicks or turns; candidates require manual review.")
