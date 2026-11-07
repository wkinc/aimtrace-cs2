# AimTrace – CS2 Demo Analysis

**Every shot leaves a trace.**

AimTrace is a Counter-Strike 2 (CS2) demo analysis project built with Python. It analyses player behaviour, aim patterns and kill statistics to help identify unusual gameplay patterns.

It also uses n8n and Ollama to generate AI-assisted reports from the analysis results.

**Important:** AimTrace is an analysis tool, not an anti-cheat system. A high suspicion score does not prove that a player is cheating. All results require manual review.

## Features

- Parse CS2 demo files (`.dem`).
- Analyse player kill statistics.
- Measure crosshair error before kills.
- Analyse aim speed and time on target.
- Calculate statistical suspicion scores.
- Compare player statistics against other players in the analysed demos.
- Display results using a Streamlit dashboard.
- Generate AI reports using Ollama and n8n.
- Save reports in timestamped folders.
- Open previous analysis results.

## Technology Stack

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| AWPy | CS2 demo parsing |
| Polars | Data processing |
| NumPy | Numerical calculations |
| Streamlit | Dashboard |
| Plotly | Data visualisation |
| n8n | AI workflow automation |
| Ollama | Local AI model |
| Qwen3 8B | AI report generation |

## Project Structure

```text
aimtrace-cs2/
│
├── ai/
│   ├── __init__.py
│   └── n8n_client.py
│
├── demos/
├── outputs/
├── cache/
│
├── app.py
├── pipeline.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Requirements

Before starting, install:

- Python 3.12
- Git
- Ollama
- Docker Desktop (optional, for running n8n)

You also need a CS2 demo file to analyse.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/wkinc/aimtrace-cs2.git
cd aimtrace-cs2
```

### 2. Create a Python virtual environment

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Ollama Setup

AimTrace uses Ollama to run the AI model locally.

1. Install Ollama from https://ollama.com/
2. Open PowerShell.
3. Download the model:

```powershell
ollama pull qwen3:8b
```

4. Make sure Ollama is running.

Check installed models:

```powershell
ollama list
```

## n8n Setup

n8n connects AimTrace to Ollama and manages the AI report workflow.

You can run n8n using Docker or install it without Docker.

### Option A: Docker Installation

1. Install Docker Desktop.
2. Start Docker Desktop.
3. Run n8n:

```powershell
docker volume create n8n_data

docker run -it --rm --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```

4. Open:

```text
http://localhost:5678
```

5. Create or import the AimTrace n8n workflow.

### Option B: Without Docker

If you do not want to use Docker, you can run n8n directly with Node.js and npm.

1. Install Node.js and npm.
2. Open PowerShell.
3. Install n8n:

```powershell
npm install n8n -g
```

4. Start n8n:

```powershell
n8n start
```

5. Open:

```text
http://localhost:5678
```

You can also try n8n without a global installation:

```powershell
npx n8n
```

Check the current n8n installation documentation for version requirements and installation changes.

### Configure the n8n Workflow

The workflow should contain:

1. Webhook
2. Basic LLM Chain
3. Ollama Chat Model
4. Respond to Webhook

Connections:

```text
Webhook
   |
   v
Basic LLM Chain
   |
   v
Respond to Webhook

Ollama Chat Model
   |
   +---- Connected to Basic LLM Chain Model input
```

Configure the Webhook node:

- HTTP Method: POST
- Respond: Using Respond to Webhook Node

Configure the Ollama Chat Model:

- Model: qwen3:8b
- Docker n8n: `http://host.docker.internal:11434`
- Non-Docker n8n: `http://localhost:11434`

Make sure your workflow is published and use its Production Webhook URL.

## Connect AimTrace to n8n

AimTrace uses an environment variable to store the webhook URL.

Windows PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("AIMTRACE_N8N_WEBHOOK", "YOUR_PRODUCTION_WEBHOOK_URL", "User")
```

Restart your terminal after setting the variable.

Check the variable:

```powershell
echo $env:AIMTRACE_N8N_WEBHOOK
```

Do not upload your personal webhook URL to GitHub.

## Run AimTrace

Activate your Python environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Start the dashboard:

```powershell
python -m streamlit run app.py
```

Then:

1. Open the Streamlit dashboard.
2. Upload a CS2 demo file or select one from the `demos` folder.
3. Adjust the analysis settings if needed.
4. Click **Run Analysis**.
5. Wait for the CS2 analysis and AI report.
6. View the AI report in the dashboard.

## Output Files

Each analysis is saved in its own timestamped folder.

Example:

```text
outputs/
└── 2026-11-07_161059/
    ├── player_scores.csv
    ├── kill_features.parquet
    ├── aim_curves.parquet
    ├── settings.json
    └── ai_analysis.json
```

| File | Description |
|---|---|
| player_scores.csv | Player statistics and suspicion scores |
| kill_features.parquet | Individual kill analysis |
| aim_curves.parquet | Aim movement data |
| settings.json | Settings used for the analysis |
| ai_analysis.json | AI-generated report |

## Demo Files

Demo files are not included in this repository.

Users must provide their own CS2 `.dem` files.

This keeps the repository smaller and avoids sharing personal gameplay data.

Place your demo files inside:

```text
demos/
```

Alternatively, upload a demo directly through the Streamlit dashboard.

## Limitations

- Results depend on the demos used for comparison.
- Small player samples can make statistical scores less reliable.
- Demo sampling may miss some movements between sampled ticks.
- High scores can have legitimate explanations.
- AI reports are based on the statistics provided to the model.
- AI-generated explanations may contain errors and must be checked.
- AimTrace does not automatically determine whether a player is cheating.

## Privacy

AimTrace can use a local Ollama model for AI report generation.

When n8n and Ollama are running locally, the analysis data is sent to your local services.

Do not expose your n8n webhook or Ollama service publicly without proper security controls.

## Future Improvements

- Better player filtering and comparison.
- More detailed aim behaviour analysis.
- Improved AI reports.
- Better visualisation of suspicious moments.
- Additional statistical features.
- Improved dashboard usability.

## Author

Developed as a personal CS2 demo analysis project.

