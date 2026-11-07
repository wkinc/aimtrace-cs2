
import json
import math
import os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def clean_data(value):
    """Convert values into safe JSON-compatible data."""
    if isinstance(value, dict):
        return {k: clean_data(v) for k, v in value.items()}

    if isinstance(value, list):
        return [clean_data(v) for v in value]

    if isinstance(value, float) and not math.isfinite(value):
        return None

    return value


def generate_ai_report(players, kills, median_err, demo_names, analysis_id, output_folder):
    webhook_url = os.getenv("AIMTRACE_N8N_WEBHOOK")

    if not webhook_url:
        print("AI report skipped: AIMTRACE_N8N_WEBHOOK is not configured.")
        return None

    # Send the top 10 players to Ollama.
    top_players = players.head(10).to_dicts()

    payload = {
        "project": "AimTrace",
        "analysis_id": analysis_id,
        "demos": demo_names,
        "summary": {
            "players_analysed": players.height,
            "kills_analysed": kills.height,
            "median_crosshair_error": median_err,
        },
        "top_players": top_players,
    }

    payload = clean_data(payload)

    try:
        request = Request(
            webhook_url,
            data=json.dumps(payload, allow_nan=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))

        report = {
            "analysis_id": analysis_id,
            "ai_response": result,
        }

        output_file = Path(output_folder) / "ai_analysis.json"
        output_file.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        print(f"AI report saved to: {output_file.resolve()}")
        return report

    except (HTTPError, URLError, TimeoutError, ValueError) as error:
        print(f"AI report failed: {error}")
        return None
