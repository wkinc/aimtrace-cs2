# AimTrace - CS2 Demo Analysis

AimTrace is a tool that analyses Counter-Strike 2 (CS2) demo files. It uses Python to collect match data and review player aim behaviour.

It also supports an optional AI report feature using n8n and Ollama.

The goal is to help players understand their gameplay through data. AimTrace is **not a cheat detector** and does not prove that a player is cheating.

## Features

- Analyse CS2 demo files.
- Review player performance and statistics.
- Calculate aim-related statistics.
- Review player aim behaviour before kills.
- Compare players in the analysed demo.
- View results in a Streamlit dashboard.
- Generate optional AI reports using n8n and Ollama.
- Save analysis results for later review.

## Technology

- Python
- Streamlit
- Polars
- NumPy
- Awpy
- Plotly
- n8n (optional)
- Ollama (optional)

## Requirements

Before installing AimTrace, prepare the following:

- Python 3.12
- Git
- Counter-Strike 2 demo file (`.dem`)
- Docker Desktop (optional, for n8n)
- Ollama (optional, for AI reports)

You do not need Docker, n8n or Ollama to use the main analysis features.

## 1. Download AimTrace

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/aimtrace-cs2.git
```

Enter the project folder:

```bash
cd aimtrace-cs2
```

## 2. Set up Python

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

On macOS or Linux:

```bash
source .venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

## 3. Add CS2 demo files

Place your CS2 demo files (`.dem`) inside the `demos/` folder.

Example:

```text
aimtrace-cs2/
└── demos/
    └── match.dem
```

You can also use the dashboard to upload a demo if the upload feature is available in your version.

**Note:** Demo files are not included in this repository. Please use your own demo files.

## 4. Run AimTrace

Start the Streamlit dashboard:

```bash
python -m streamlit run app.py
```

Open the local address shown in your terminal. It is usually:

```text
http://localhost:8501
```

Follow the dashboard instructions to analyse your demo.

## 5. Optional: Set up AI reports

AimTrace can use n8n and Ollama to generate AI reports from the analysis results.

This feature is optional. The main analysis features can work without it.

### Step 1: Install Ollama

Download Ollama from:

https://ollama.com/

After installation, open a terminal and download the model:

```bash
ollama pull qwen3:8b
```

Make sure Ollama is running.

You can check it with:

```bash
ollama list
```

### Step 2: Install n8n using Docker

Install Docker Desktop:

https://www.docker.com/products/docker-desktop/

The repository includes a `docker-compose.yml` file.

Start n8n from the AimTrace project folder:

```bash
docker compose up -d
```

Open n8n:

```text
http://localhost:5678
```

Create your own n8n account and complete the initial setup.

To stop n8n:

```bash
docker compose down
```

Your n8n workflows and settings are stored in a Docker volume, so they remain after the container stops.

### Step 3: Configure your timezone

The Docker Compose setup uses UTC as its default timezone. You can change it to your local timezone.

Create a file named `.env` in the same folder as `docker-compose.yml`.

Add your timezone:

```env
GENERIC_TIMEZONE=Asia/Kuala_Lumpur
```

Examples:

| Location | Timezone |
|---|---|
| Malaysia | `Asia/Kuala_Lumpur` |
| New York | `America/New_York` |
| Los Angeles | `America/Los_Angeles` |
| London | `Europe/London` |
| Tokyo | `Asia/Tokyo` |

Make sure your `docker-compose.yml` uses the `GENERIC_TIMEZONE` variable for both `TZ` and `GENERIC_TIMEZONE`.

After changing the timezone, restart n8n:

```bash
docker compose down
docker compose up -d
```

### Step 4: Install n8n without Docker (Alternative)

If you do not want to use Docker, you can install n8n using npm.

First, install Node.js:

https://nodejs.org/

Then install n8n:

```bash
npm install n8n -g
```

Start n8n:

```bash
n8n start
```

You can also start it without a global installation:

```bash
npx n8n
```

Open:

```text
http://localhost:5678
```

For more installation options, check the official n8n documentation:

https://docs.n8n.io/hosting/installation/

### Step 5: Create the n8n workflow

Create a new workflow in n8n with these nodes:

1. **Webhook** - receives analysis data from AimTrace.
2. **Basic LLM Chain** - sends the data to the AI model.
3. **Ollama Chat Model** - connects to your local Ollama model.
4. **Respond to Webhook** - sends the AI response back to AimTrace.

Connect the nodes correctly and configure the Ollama model.

For the Ollama connection, use the following base URL:

**If n8n runs in Docker:**

```text
http://host.docker.internal:11434
```

**If n8n runs directly on your computer:**

```text
http://localhost:11434
```

Select your downloaded model, such as `qwen3:8b`.

Configure the Webhook node:

- HTTP Method: `POST`
- Respond: `Using Respond to Webhook Node`

Make sure the workflow returns an AI response in the expected format.

### Step 6: Connect AimTrace to n8n

In your n8n Webhook node, copy the **Production URL**.

Publish your workflow before using the Production URL.

Set the webhook URL as an environment variable.

On Windows PowerShell:

```powershell
[Environment]::SetEnvironmentVariable(
    "AIMTRACE_N8N_WEBHOOK",
    "YOUR_N8N_PRODUCTION_WEBHOOK_URL",
    "User"
)
```

On macOS or Linux:

```bash
export AIMTRACE_N8N_WEBHOOK="YOUR_N8N_PRODUCTION_WEBHOOK_URL"
```

Replace the example URL with your own Production URL.

Restart your terminal or application after setting the variable.

AimTrace will use this URL to send analysis data to n8n.

**Important:** Do not upload your private webhook URL, API keys or passwords to GitHub.

## Project Structure

```text
aimtrace-cs2/
│
├── ai/
│   ├── __init__.py
│   └── n8n_client.py
│
├── demos/
├── cache/
├── outputs/
├── reports/
│
├── .streamlit/
│   └── config.toml
│
├── app.py
├── pipeline.py
├── analyze_aim.py
├── analyze_demo.py
├── analyze_movement.py
├── export_demo.py
├── review_aim.py
├── run_analysis.py
│
├── docker-compose.yml
├── requirements.txt
├── .gitignore
└── README.md
```

Some folders are created automatically when AimTrace runs.

## Analysis Results

AimTrace saves analysis results in the output folders.

Depending on the analysis, results may include:

- Player scores
- Kill-related features
- Aim curves
- Analysis settings
- AI-generated reports

Each analysis can have its own output folder to keep previous results separate.

## Important Notes

- AimTrace is a learning and analysis project.
- Its scores are based on the data available in the analysed demos.
- A high score does not mean a player is cheating.
- Results can be affected by demo quality, player behaviour and other factors.
- AI reports are generated from the available analysis data. They may not always be correct.
- Do not share private demo files or personal player information without permission.
- Users are responsible for their own Ollama and n8n setup.

## Troubleshooting

**Streamlit does not start**

Check that your virtual environment is active and the required packages are installed.

```bash
pip install -r requirements.txt
```

**Ollama connection failed**

Make sure Ollama is running and the selected model is installed.

```bash
ollama list
```

**n8n webhook does not work**

Check that:

- Your n8n workflow is published.
- You copied the Production URL.
- Your `AIMTRACE_N8N_WEBHOOK` variable is correct.
- Your n8n and Ollama services are running.

**Demo file cannot be analysed**

Make sure the file is a valid CS2 demo file and that it is placed in the correct folder.

## Future Improvements

- Improve aim behaviour analysis.
- Add more player comparison features.
- Improve the dashboard and filtering.
- Improve AI report quality.
- Support more analysis methods.

## License

Add your chosen open-source license here before publishing the project.
