from pathlib import Path
import sys

import numpy as np
import polars as pl
from awpy import Demo

# ---------- Settings ----------
DEMOS_FOLDER = Path("demos")
CACHE_FOLDER = Path("cache")
REPORTS_FOLDER = Path("reports")

SAMPLE_EVERY_TICKS = 2     # lower = more detail, but slower and bigger
WINDOW_SECONDS = 1.0       # time before each kill that we look at
ON_TARGET_DEGREES = 3.0    # "on target" means crosshair error <= this
EYE_HEIGHT = 64.0          # attacker eye height (units)
TARGET_HEIGHT = 56.0       # aim point on the victim (units)
MIN_KILLS = 1             # ignore players with fewer kills
FLIP_PITCH = False         # set True if the sanity check shows a huge error

# feature name -> direction (+1 = higher is more suspicious, -1 = lower is)
FEATURES = {
    "headshot_pct": +1,
    "smoke_kill_pct": +1,
    "blind_kill_pct": +1,
    "wallbang_pct": +1,
    "err_at_kill_med": -1,
    "time_on_target_med": -1,
    "speed_p90": +1,
}


# ---------- Step 1: load demo (with cache) ----------
def load_demo(path: Path):
    cache = CACHE_FOLDER / f"{path.stem}_every{SAMPLE_EVERY_TICKS}"
    names = ["kills", "snapshots"]
    files = {n: cache / f"{n}.parquet" for n in names}
    rate_file = cache / "tick_rate.txt"

    if all(f.exists() for f in files.values()) and rate_file.exists():
        print(f"  using cache for {path.name}")
        data = {n: pl.read_parquet(f) for n, f in files.items()}
        return data, float(rate_file.read_text())

    print(f"  parsing {path.name} (this can take a while)")
    cache.mkdir(parents=True, exist_ok=True)
    demo = Demo(str(path))
    demo.load("shots", "kills", "damages")
    snapshots = demo.snapshots(every=SAMPLE_EVERY_TICKS)
    if snapshots.is_empty():
        raise RuntimeError(f"No snapshots in {path.name}. Is it a valid CS2 demo?")

    data = {"kills": demo.kills, "snapshots": snapshots}
    for n, frame in data.items():
        frame.write_parquet(files[n])
    tick_rate = float(demo.tick_rate or 64.0)
    rate_file.write_text(str(tick_rate))
    return data, tick_rate


# ---------- Step 2: features for every kill ----------
def build_kill_features(data, tick_rate, demo_id):
    kills = data["kills"]
    snaps = data["snapshots"]

    # Make sure optional columns exist
    for col, default in [("thrusmoke", False), ("attackerblind", False),
                         ("penetrated", 0), ("noscope", False),
                         ("headshot", False), ("distance", None),
                         ("weapon", None), ("victim_name", None),
                         ("round_num", None)]:
        if col not in kills.columns:
            kills = kills.with_columns(pl.lit(default).alias(col))

    kills = kills.with_columns(
        pl.col("attacker_steamid").cast(pl.Utf8),
        pl.col("victim_steamid").cast(pl.Utf8),
    ).filter(
        pl.col("attacker_steamid").is_not_null()
        & pl.col("victim_steamid").is_not_null()
        & (pl.col("attacker_steamid") != "0")                       # bots / world
        & (pl.col("attacker_steamid") != pl.col("victim_steamid"))  # suicide
    ).with_row_index("kill_id")

    if kills.is_empty():
        return None, None

    snaps = snaps.select(["tick", "steamid", "x", "y", "z", "pitch", "yaw"]).with_columns(
        pl.col("steamid").cast(pl.Utf8)
    ).drop_nulls()

    window = int(WINDOW_SECONDS * tick_rate)

    # Keep only snapshots that are within WINDOW before some kill (saves memory)
    kill_ticks = np.sort(kills["tick"].to_numpy())
    snap_ticks = snaps["tick"].to_numpy()
    idx = np.searchsorted(kill_ticks, snap_ticks, side="left")
    idx_clip = np.minimum(idx, len(kill_ticks) - 1)
    keep = (idx < len(kill_ticks)) & ((kill_ticks[idx_clip] - snap_ticks) <= window)
    snaps = snaps.filter(pl.Series(keep))

    att = snaps.select(
        "tick",
        pl.col("steamid").alias("attacker_steamid"),
        pl.col("x").alias("ax"), pl.col("y").alias("ay"), pl.col("z").alias("az"),
        "pitch", "yaw",
    )
    vic = snaps.select(
        "tick",
        pl.col("steamid").alias("victim_steamid"),
        pl.col("x").alias("vx"), pl.col("y").alias("vy"), pl.col("z").alias("vz"),
    )
    k = kills.select(
        "kill_id", pl.col("tick").alias("kill_tick"),
        "attacker_steamid", "victim_steamid",
    )

    w = (
        k.join(att, on="attacker_steamid")
        .filter((pl.col("tick") <= pl.col("kill_tick"))
                & (pl.col("tick") >= pl.col("kill_tick") - window))
        .join(vic, on=["victim_steamid", "tick"])
        .sort(["kill_id", "tick"])
    )
    if w.is_empty():
        return None, None

    # Crosshair error = angle between where you look and where the enemy is
    dx = (w["vx"] - w["ax"]).to_numpy()
    dy = (w["vy"] - w["ay"]).to_numpy()
    dz = ((w["vz"] + TARGET_HEIGHT) - (w["az"] + EYE_HEIGHT)).to_numpy()
    target_yaw = np.degrees(np.arctan2(dy, dx))
    target_pitch = np.degrees(np.arctan2(dz, np.hypot(dx, dy)))
    if not FLIP_PITCH:
        target_pitch = -target_pitch
    yaw = w["yaw"].to_numpy()
    pitch = w["pitch"].to_numpy()
    d_yaw = np.mod(yaw - target_yaw + 180.0, 360.0) - 180.0
    d_pitch = pitch - target_pitch
    err = np.hypot(d_yaw, d_pitch)

    # Aim speed between samples of the same kill (degrees per second)
    kid = w["kill_id"].to_numpy()
    ticks = w["tick"].to_numpy().astype(float)
    same = np.concatenate([[False], kid[1:] == kid[:-1]])
    dyaw = np.concatenate([[np.nan], np.mod(np.diff(yaw) + 180.0, 360.0) - 180.0])
    dpitch = np.concatenate([[np.nan], np.diff(pitch)])
    dt = np.concatenate([[np.nan], np.diff(ticks)]) / tick_rate
    with np.errstate(divide="ignore", invalid="ignore"):
        speed = np.hypot(dyaw, dpitch) / dt
    speed = np.where(same & np.isfinite(speed), speed, np.nan)

    w = w.with_columns(
        pl.Series("err", err),
        pl.Series("speed", speed, nan_to_null=True),
    )

    curves = w.select(
        "kill_id", "tick", "err", "speed",
        ((pl.col("tick") - pl.col("kill_tick")) / tick_rate).alias("seconds_before_kill"),
    ).with_columns(pl.lit(demo_id).alias("demo"))

    feats = w.group_by("kill_id").agg(
        pl.col("err").first().alias("err_start"),
        pl.col("err").last().alias("err_at_kill"),
        pl.col("err").min().alias("err_min"),
        pl.col("speed").max().alias("peak_speed"),
        pl.col("tick").filter(pl.col("err") > ON_TARGET_DEGREES).max().alias("last_off_tick"),
        pl.col("tick").last().alias("last_tick"),
        pl.col("kill_tick").first().alias("kill_tick"),
        pl.len().alias("samples"),
    ).filter(pl.col("samples") >= 3)

    # Time the crosshair stayed on target before the kill
    #  - never off target in the window -> full window
    #  - off target at the last sample -> 0
    feats = feats.with_columns(
        pl.when(pl.col("last_off_tick").is_null())
        .then(pl.lit(WINDOW_SECONDS * 1000))
        .when(pl.col("last_off_tick") == pl.col("last_tick"))
        .then(pl.lit(0.0))
        .otherwise((pl.col("kill_tick") - pl.col("last_off_tick")) / tick_rate * 1000)
        .alias("time_on_target_ms")
    ).drop("last_off_tick", "last_tick", "kill_tick")

    out = kills.join(feats, on="kill_id").with_columns(
        pl.lit(demo_id).alias("demo"),
        pl.col("thrusmoke").cast(pl.Boolean).fill_null(False),
        pl.col("attackerblind").cast(pl.Boolean).fill_null(False),
        (pl.col("penetrated").cast(pl.Float64).fill_null(0) > 0).alias("wallbang"),
        pl.col("headshot").cast(pl.Boolean).fill_null(False),
    )
    return out, curves


# ---------- Step 3: one row per player ----------
def summarise_players(kf: pl.DataFrame) -> pl.DataFrame:
    return kf.group_by("attacker_steamid").agg(
        pl.col("attacker_name").last().alias("player"),
        pl.len().alias("kills"),
        (pl.col("headshot").cast(pl.Float64).mean() * 100).alias("headshot_pct"),
        (pl.col("thrusmoke").cast(pl.Float64).mean() * 100).alias("smoke_kill_pct"),
        (pl.col("attackerblind").cast(pl.Float64).mean() * 100).alias("blind_kill_pct"),
        (pl.col("wallbang").cast(pl.Float64).mean() * 100).alias("wallbang_pct"),
        pl.col("err_at_kill").median().alias("err_at_kill_med"),
        pl.col("err_start").median().alias("err_start_med"),
        pl.col("time_on_target_ms").median().alias("time_on_target_med"),
        pl.col("peak_speed").quantile(0.9).alias("speed_p90"),
    )


def add_suspicion_score(players: pl.DataFrame) -> pl.DataFrame:
    p = players.filter(pl.col("kills") >= MIN_KILLS)
    if p.height < 5:
        print("Warning: very few players. z-scores are not reliable. Add more demos.")
    z_cols = []
    for feature, sign in FEATURES.items():
        mean, std = p[feature].mean(), p[feature].std()
        name = f"z_{feature}"
        if mean is None or std is None or std == 0:
            p = p.with_columns(pl.lit(0.0).alias(name))
        else:
            p = p.with_columns(((pl.col(feature) - mean) / std * sign).alias(name))
        z_cols.append(name)
    return p.with_columns(
        pl.mean_horizontal(z_cols).alias("suspicion_score"),
        pl.sum_horizontal([(pl.col(c) > 2).cast(pl.Int32) for c in z_cols]).alias("features_above_2sd"),
    ).sort("suspicion_score", descending=True)


# ---------- Run ----------
def run(demo_paths, out_folder, progress=None, log=print):
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)

    all_kills, all_curves = [], []
    total = len(demo_paths)
    for i, path in enumerate(demo_paths):
        if progress:
            progress(i / total, f"Demo {i + 1} of {total}: {path.name}")
        log(f"Demo: {path.name}")
        try:
            data, tick_rate = load_demo(path)
            kf, curves = build_kill_features(data, tick_rate, path.stem)
        except Exception as e:  # one bad demo should not stop the whole run
            log(f"  FAILED: {e}")
            continue
        if kf is None or kf.is_empty():
            log("  no usable kills, skipped")
            continue
        all_kills.append(kf)
        all_curves.append(curves)
        log(f"  kills with features: {kf.height}")

    if not all_kills:
        raise RuntimeError("No kill features were created. Check the demo files.")

    kills = pl.concat(all_kills, how="diagonal_relaxed")
    kills.write_parquet(out_folder / "kill_features.parquet")
    pl.concat(all_curves).write_parquet(out_folder / "aim_curves.parquet")

    players = add_suspicion_score(summarise_players(kills))
    players.write_csv(out_folder / "player_scores.csv")

    if progress:
        progress(1.0, "Done")
    median_err = kills["err_at_kill"].median()
    log(f"Median crosshair error at kill: {median_err:.2f} degrees")
    return players, kills, median_err


def main():
    from datetime import datetime

    demo_paths = sorted(DEMOS_FOLDER.glob("*.dem"))
    if len(sys.argv) > 1:
        demo_paths = [Path(a) for a in sys.argv[1:]]
    if not demo_paths:
        raise FileNotFoundError(f"No .dem files found in {DEMOS_FOLDER.resolve()}")
    out = Path("outputs") / datetime.now().strftime("%Y-%m-%d_%H%M%S")
    players, _, _ = run(demo_paths, out)
    print(players.head(10))
    print(f"Saved to: {out.resolve()}")


if __name__ == "__main__":
    main()

