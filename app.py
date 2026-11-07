
import json
from datetime import datetime
from pathlib import Path

import plotly.express as px
import polars as pl
import streamlit as st

import pipeline
from ai.n8n_client import generate_ai_report


DEMOS = Path("demos")
OUTPUTS = Path("outputs")

DEMOS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)


st.set_page_config(
    page_title="CS2 Demo Review",
    page_icon="🎯",
    layout="wide",
)

st.title("CS2 Demo Analysis Dashboard")
st.caption(
    "A high score is a reason to watch the demo. "
    "It is not proof of cheating."
)


FEATURE_LABELS = {
    "headshot_pct": "Headshot kills (%)",
    "smoke_kill_pct": "Kills through smoke (%)",
    "blind_kill_pct": "Kills while blind (%)",
    "wallbang_pct": "Wallbang kills (%)",
    "err_at_kill_med": "Crosshair error at kill (deg, median)",
    "time_on_target_med": "Time on target before kill (ms, median)",
    "speed_p90": "Aim speed, top 10% (deg/s)",
}


# ==========================================================
# SIDEBAR: NEW ANALYSIS
# ==========================================================

st.sidebar.header("New analysis")

uploads = st.sidebar.file_uploader(
    "Upload demo files (.dem)",
    type=["dem"],
    accept_multiple_files=True,
)

existing = sorted(
    p.name for p in DEMOS.glob("*.dem")
)

picked = st.sidebar.multiselect(
    "Or use demos already in the demos folder",
    existing,
)


with st.sidebar.expander("Settings"):

    every = st.slider(
        "Sample every N ticks",
        1, 8, 2,
    )

    window = st.slider(
        "Seconds before each kill",
        0.5, 3.0, 1.0, 0.5,
    )

    on_target = st.slider(
        "On target (degrees)",
        1.0, 10.0, 3.0, 0.5,
    )

    min_kills_run = st.number_input(
        "Minimum kills per player",
        1, 100, 1,
    )

    flip = st.checkbox(
        "Flip pitch (use if crosshair error is huge)"
    )


# ==========================================================
# RUN ANALYSIS
# ==========================================================

if st.sidebar.button("Run analysis", type="primary"):

    chosen_paths = {}

    for file in uploads:

        target = DEMOS / file.name
        target.write_bytes(file.getbuffer())

        chosen_paths[file.name] = target

    for name in picked:

        chosen_paths[name] = DEMOS / name

    if not chosen_paths:

        st.sidebar.error(
            "Upload or choose at least one demo."
        )

        st.stop()

    # Apply pipeline settings.
    pipeline.SAMPLE_EVERY_TICKS = every
    pipeline.WINDOW_SECONDS = window
    pipeline.ON_TARGET_DEGREES = on_target
    pipeline.MIN_KILLS = int(min_kills_run)
    pipeline.FLIP_PITCH = flip

    # Create timestamped analysis folder.
    run_name = datetime.now().strftime(
        "%Y-%m-%d_%H%M%S"
    )

    out = OUTPUTS / run_name

    bar = st.progress(
        0.0,
        text="Starting...",
    )

    with st.status(
        "Running analysis. The first run of a demo can take a few minutes.",
        expanded=True,
    ) as status:

        try:

            # Run the existing CS2 analysis pipeline.
            players, analyzed_kills, median_err = pipeline.run(
                list(chosen_paths.values()),
                out,
                progress=lambda frac, text: bar.progress(
                    frac,
                    text=text,
                ),
                log=st.write,
            )

            # Save analysis settings.
            settings = {
                "demos": list(chosen_paths),
                "sample_every_ticks": every,
                "window_seconds": window,
                "on_target_degrees": on_target,
                "min_kills": int(min_kills_run),
                "flip_pitch": flip,
            }

            (out / "settings.json").write_text(
                json.dumps(settings, indent=2),
                encoding="utf-8",
            )

            status.update(
                label="CS2 analysis finished",
                state="complete",
                expanded=False,
            )

            st.session_state["selected_run"] = run_name

        except Exception as error:

            status.update(
                label="Analysis failed",
                state="error",
            )

            st.error(str(error))
            st.stop()

    # ======================================================
    # GENERATE AI REPORT
    # ======================================================

    with st.status(
        "Generating AI report using Ollama...",
        expanded=True,
    ) as ai_status:

        ai_report = generate_ai_report(
            players=players,
            kills=analyzed_kills,
            median_err=median_err,
            demo_names=list(chosen_paths.keys()),
            analysis_id=run_name,
            output_folder=out,
        )

        if ai_report:

            ai_status.update(
                label="AI report generated successfully",
                state="complete",
                expanded=False,
            )

        else:

            ai_status.update(
                label="AI report unavailable. CS2 analysis is still saved.",
                state="error",
                expanded=False,
            )


# ==========================================================
# SIDEBAR: OPEN SAVED ANALYSIS
# ==========================================================

runs = sorted(
    [
        folder.name
        for folder in OUTPUTS.iterdir()
        if folder.is_dir()
        and (folder / "player_scores.csv").exists()
    ],
    reverse=True,
)


if not runs:

    st.info(
        "Upload demo files in the sidebar and press Run analysis."
    )

    st.stop()


st.sidebar.divider()

selected = st.sidebar.selectbox(
    "Open a saved run",
    runs,
    key="selected_run",
)

folder = OUTPUTS / selected

st.sidebar.caption(
    f"Saved in: `{folder.resolve()}`"
)


st.sidebar.download_button(
    "Download player_scores.csv",
    (folder / "player_scores.csv").read_bytes(),
    file_name=f"player_scores_{selected}.csv",
)


# ==========================================================
# LOAD ANALYSIS DATA
# ==========================================================

@st.cache_data
def load_data(folder_str, stamp):

    f = Path(folder_str)

    scores = pl.read_csv(
        f / "player_scores.csv"
    ).with_columns(
        pl.col("attacker_steamid").cast(pl.Utf8)
    )

    kills = pl.read_parquet(
        f / "kill_features.parquet"
    ).with_columns(
        pl.col("attacker_steamid").cast(pl.Utf8)
    )

    curves_path = f / "aim_curves.parquet"

    curves = (
        pl.read_parquet(curves_path)
        if curves_path.exists()
        else None
    )

    return scores, kills, curves


scores, kills, curves = load_data(
    str(folder),
    (folder / "player_scores.csv").stat().st_mtime,
)


# ==========================================================
# SECTION 1: AI ANALYSIS
# ==========================================================

st.divider()
st.header("1. AI Analysis")

ai_file = folder / "ai_analysis.json"

if ai_file.exists():

    try:

        with ai_file.open(
            "r",
            encoding="utf-8",
        ) as file:

            ai_data = json.load(file)

        st.caption(
            f"Analysis ID: {ai_data.get('analysis_id', selected)}"
        )

        st.caption(
            f"Generated: {ai_data.get('generated_at', 'Unknown')}"
        )

        analysis_text = ai_data.get("analysis", "")

        if not analysis_text:
            response = ai_data.get("response", {})
            analysis_text = response.get("analysis", "")

        if not analysis_text:
            response = ai_data.get("ai_response", {})
            analysis_text = response.get("analysis", "")

        if not analysis_text:
            st.warning("The AI report does not contain an analysis.")
        else:
            st.markdown(analysis_text)

        with st.expander("View raw AI response"):

            st.json(ai_data.get("response", {}))

        st.download_button(
            "Download AI report",
            data=ai_file.read_bytes(),
            file_name=f"ai_analysis_{selected}.json",
            mime="application/json",
        )

    except (OSError, json.JSONDecodeError) as error:

        st.error(f"Could not load AI report: {error}")

else:

    st.info(
        "No AI report is available for this analysis. "
        "Run a new analysis with the n8n workflow active."
    )


# ==========================================================
# DISPLAY FILTER
# ==========================================================

st.sidebar.header("Display filter")

min_kills = st.sidebar.slider(
    "Minimum kills",
    1, 60, 1,
)

scores = scores.filter(
    pl.col("kills") >= min_kills
)

if scores.is_empty():

    st.info("No players match the filter.")
    st.stop()


# ==========================================================
# SECTION 2: TOP METRICS
# ==========================================================

st.divider()
st.header("2. Overview")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Players",
    scores.height,
)

c2.metric(
    "Kills analysed",
    int(kills.height),
)

c3.metric(
    "Demos",
    kills["demo"].n_unique(),
)

c4.metric(
    "Players with 2+ flags",
    int(
        (scores["features_above_2sd"] >= 2).sum()
    ),
)


# ==========================================================
# SECTION 3: RANKING
# ==========================================================

st.divider()
st.header("3. Ranking")

st.subheader(
    "Players ranked by suspicion score"
)

show_cols = [
    c for c in [
        "player",
        "kills",
        "suspicion_score",
        "features_above_2sd",
        *FEATURE_LABELS.keys(),
    ]
    if c in scores.columns
]

st.dataframe(
    scores.select(show_cols).with_columns(
        pl.col(pl.Float64).round(2)
    ),
    use_container_width=True,
    hide_index=True,
)


fig = px.bar(
    scores.head(20).to_pandas(),
    x="player",
    y="suspicion_score",
    title="Top 20 by suspicion score",
)

st.plotly_chart(
    fig,
    use_container_width=True,
)


# ==========================================================
# SECTION 4: PLAYER REVIEW
# ==========================================================

st.divider()
st.header("4. Player review")

names = scores["player"].to_list()

chosen = st.selectbox(
    "Player",
    names,
)

row = scores.filter(
    pl.col("player") == chosen
).row(0, named=True)

steamid = row["attacker_steamid"]


m1, m2, m3, m4 = st.columns(4)

m1.metric(
    "Kills",
    row["kills"],
)

m2.metric(
    "Suspicion score",
    f"{row['suspicion_score']:.2f}",
)

m3.metric(
    "Features above 2 SD",
    row["features_above_2sd"],
)

m4.metric(
    "Headshot %",
    f"{row['headshot_pct']:.0f}",
)


pk = kills.filter(
    pl.col("attacker_steamid") == steamid
).sort("err_at_kill")


st.markdown(
    "**Kills (sorted by crosshair error, smallest first)**"
)

kill_cols = [
    c for c in [
        "demo",
        "tick",
        "round_num",
        "victim_name",
        "weapon",
        "distance",
        "err_start",
        "err_at_kill",
        "time_on_target_ms",
        "peak_speed",
        "headshot",
        "thrusmoke",
        "attackerblind",
        "wallbang",
    ]
    if c in pk.columns
]

st.dataframe(
    pk.select(kill_cols).with_columns(
        pl.col(pl.Float64).round(2)
    ),
    use_container_width=True,
    hide_index=True,
)


# ==========================================================
# LOOK AT ONE KILL
# ==========================================================

st.markdown("**Look at one kill**")

if pk.height == 0:

    st.info("No kill records available for this player.")

else:

    labels = [
        (
            f"{i + 1}. {r['demo']} | tick {r['tick']} | "
            f"{r.get('victim_name', '?')} | {r.get('weapon', '?')}"
        )
        for i, r in enumerate(pk.to_dicts())
    ]

    idx = st.selectbox(
        "Kill",
        range(len(labels)),
        format_func=lambda i: labels[i],
    )

    kill = pk.row(
        idx,
        named=True,
    )

    st.write(
        f"Tick **{kill['tick']}**. Use this tick to jump "
        "to the moment in the CS2 demo viewer "
        f"(`demo_gototick {max(kill['tick'] - 128, 0)}`)."
    )

    # ==================================================
    # AIM CURVES
    # ==================================================

    if curves is None:

        st.info(
            "Run the pipeline again to create aim_curves.parquet."
        )

    else:

        curve = curves.filter(
            (pl.col("demo") == kill["demo"])
            & (pl.col("kill_id") == kill["kill_id"])
        ).sort("seconds_before_kill")

        if curve.height:

            g1, g2 = st.columns(2)

            with g1:

                fig = px.line(
                    curve.to_pandas(),
                    x="seconds_before_kill",
                    y="err",
                    markers=True,
                    labels={
                        "err": "Crosshair error (deg)",
                        "seconds_before_kill": "Seconds before kill",
                    },
                    title="Crosshair error before the kill (0 = enemy killed)",
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True,
                )

            with g2:

                fig2 = px.line(
                    curve.to_pandas(),
                    x="seconds_before_kill",
                    y="speed",
                    markers=True,
                    labels={
                        "speed": "Aim speed (deg/s)",
                        "seconds_before_kill": "Seconds before kill",
                    },
                    title="Aim speed before the kill",
                )

                st.plotly_chart(
                    fig2,
                    use_container_width=True,
                )


# ==========================================================
# SECTION 5: COMPARE TO THE CROWD
# ==========================================================

st.divider()
st.header("5. Compare to the crowd")

st.caption(
    f"The red line is the player selected in section 4: {chosen}"
)

available_features = [
    feature
    for feature in FEATURE_LABELS
    if feature in scores.columns
]

feature = st.selectbox(
    "Feature",
    available_features,
    format_func=lambda f: FEATURE_LABELS[f],
)

fig = px.histogram(
    scores.to_pandas(),
    x=feature,
    nbins=30,
    title=FEATURE_LABELS[feature],
)

player_value = scores.filter(
    pl.col("player") == chosen
)[feature][0]

if player_value is not None:

    fig.add_vline(
        x=player_value,
        line_dash="dash",
        line_color="red",
        annotation_text=chosen,
    )

st.plotly_chart(
    fig,
    use_container_width=True,
)


# ==========================================================
# FINAL WARNING
# ==========================================================

st.warning(
    "Fast or very accurate aim can be legitimate. "
    "Sampling can miss movement between ticks, and results "
    "depend on how many demos you used for the baseline. "
    "Always review the demo."
)
