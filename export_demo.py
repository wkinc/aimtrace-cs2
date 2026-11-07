from pathlib import Path
import sys

from awpy import Demo
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment


demo_path = Path("demos/sample.dem")
if not demo_path.exists():
    raise FileNotFoundError(f"Demo not found: {demo_path.resolve()}")

output_folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("reports")
output_folder.mkdir(parents=True, exist_ok=True)

demo = Demo(str(demo_path))
demo.load("shots", "kills", "damages")

workbook = Workbook()
workbook.remove(workbook.active)

for sheet_name, frame in [
    ("Shots", demo.shots),
    ("Kills", demo.kills),
    ("Damages", demo.damages),
]:
    sheet = workbook.create_sheet(sheet_name)
    columns = list(frame.columns)
    sheet.append(columns)

    for row in frame.iter_rows(named=False):
        # Convert values to Excel-friendly values where possible.
        sheet.append([None if value is None else value for value in row])

    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center")

    for column in sheet.columns:
        letter = column[0].column_letter
        max_length = max((len(str(cell.value or "")) for cell in column), default=0)
        sheet.column_dimensions[letter].width = min(max_length + 2, 35)

output_file = output_folder / "cs2_demo_analysis.xlsx"
workbook.save(output_file)

print("Demo export complete!")
print(f"Shots: {demo.shots.height}")
print(f"Kills: {demo.kills.height}")
print(f"Damage events: {demo.damages.height}")
print(f"Saved to: {output_file.resolve()}")
