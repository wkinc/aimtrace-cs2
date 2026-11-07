from pathlib import Path
from collections import defaultdict
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

players = {}
weapon_usage = defaultdict(int)


def get_player_key(steamid, name):
    return str(steamid) if steamid else str(name)


def get_player(steamid, name):
    key = get_player_key(steamid, name)
    if key not in players:
        players[key] = {
            "Steam ID": steamid,
            "Player": name or "Unknown",
            "Shot Events": 0,
            "Kills": 0,
            "Headshot Kills": 0,
            "Damage Dealt": 0,
        }
    return key


for row in demo.shots.iter_rows(named=True):
    key = get_player(row["steamid"], row["name"])
    players[key]["Shot Events"] += 1
    weapon_usage[(key, row["weapon"] or "Unknown")] += 1

for row in demo.kills.iter_rows(named=True):
    key = get_player(row["attacker_steamid"], row["attacker_name"])
    players[key]["Kills"] += 1
    if row["headshot"] is True:
        players[key]["Headshot Kills"] += 1

for row in demo.damages.iter_rows(named=True):
    key = get_player(row["attacker_steamid"], row["attacker_name"])
    players[key]["Damage Dealt"] += row["dmg_health"] or 0

workbook = Workbook()
summary = workbook.active
summary.title = "Player Summary"

headers = [
    "Steam ID", "Player", "Shot Events", "Kills", "Headshot Kills",
    "Headshot Share of Kills (%)", "Damage Dealt",
]
summary.append(headers)

for stats in sorted(players.values(), key=lambda item: item["Kills"], reverse=True):
    kills = stats["Kills"]
    headshots = stats["Headshot Kills"]
    headshot_share = round(headshots / kills * 100, 2) if kills > 0 else 0
    summary.append([
        stats["Steam ID"], stats["Player"], stats["Shot Events"], kills,
        headshots, headshot_share, stats["Damage Dealt"],
    ])

weapons_sheet = workbook.create_sheet("Weapon Usage")
weapons_sheet.append(["Steam ID", "Player", "Weapon", "Shot Events"])
for (key, weapon), count in sorted(weapon_usage.items(), key=lambda item: item[1], reverse=True):
    stats = players[key]
    weapons_sheet.append([stats["Steam ID"], stats["Player"], weapon, count])

for sheet in workbook.worksheets:
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

output_file = output_folder / "player_analysis.xlsx"
workbook.save(output_file)

print("Player analysis complete!")
print(f"Players found: {len(players)}")
print(f"Saved to: {output_file.resolve()}")
