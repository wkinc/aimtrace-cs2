from pathlib import Path
import sys

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill


output_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports")
input_file = output_folder / "aim_angle_analysis.xlsx"
output_file = output_folder / "aim_review.xlsx"

if not input_file.exists():
    raise FileNotFoundError(
        f"Could not find {input_file}. Run analyze_aim.py first, using the same output folder."
    )

source_wb = load_workbook(input_file, read_only=True, data_only=True)
source_ws = source_wb["Aim Changes"]
rows = source_ws.iter_rows(values_only=True)
headers = next(rows, None)

if not headers:
    raise ValueError("The aim-angle worksheet is empty.")

header_index = {str(name): i for i, name in enumerate(headers)}
required = [
    "Steam ID", "Player", "Previous Tick", "Current Tick", "Tick Gap",
    "Pitch Change (degrees)", "Yaw Change (degrees)",
    "Combined Angle Change (degrees)",
]
missing = [name for name in required if name not in header_index]
if missing:
    raise ValueError(f"Missing expected columns: {missing}")

review_rows = []
for row in rows:
    tick_gap = row[header_index["Tick Gap"]]
    angle_change = row[header_index["Combined Angle Change (degrees)"]]
    if tick_gap is None or angle_change is None:
        continue
    if tick_gap <= 8 and angle_change >= 15:
        review_rows.append([row[header_index[name]] for name in required])

source_wb.close()

workbook = Workbook()
sheet = workbook.active
sheet.title = "Review Shortlist"
sheet.append(required)
for row in review_rows:
    sheet.append(row)

sheet.freeze_panes = "A2"
sheet.auto_filter.ref = sheet.dimensions
for cell in sheet[1]:
    cell.font = Font(bold=True, color="FFFFFF")
    cell.fill = PatternFill(fill_type="solid", fgColor="1F4E78")
for column in sheet.columns:
    letter = column[0].column_letter
    max_length = max((len(str(cell.value or "")) for cell in column), default=0)
    sheet.column_dimensions[letter].width = min(max_length + 2, 38)

workbook.save(output_file)
print("Aim review shortlist complete!")
print(f"Events shortlisted for manual review: {len(review_rows)}")
print(f"Saved to: {output_file.resolve()}")
print("Shortlisted events are review candidates, not proof of cheating.")
