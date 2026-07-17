from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AnalysisConfig:
    header_size_bytes: int = 27
    size_threshold_bytes: int = 5 * 1024
    theoretical_fps: float = 72.0
    packet_gap_threshold_s: float = 0.005
    long_gap_factor: float = 3.0
    high_variation_s: float = 0.010
    alignment_tolerance_s: float = 0.005

    @property
    def theoretical_ifi_s(self) -> float:
        return 1.0 / self.theoretical_fps


SSQ_COLUMNS = {
    "general_discomfort": "General discomfort",
    "fatigue": "Fatigue",
    "headache": "Headache",
    "eyestrain": "Eyestrain",
    "difficulty_focusing": "Difficulty focusing",
    "increased_salivation": "Increased salivation",
    "sweating": "Sweating",
    "nausea": "Nausea",
    "difficulty_concentrating": "Difficulty concentrating",
    "fullness_head": "Fullness of the head",
    "blurred_vision": "Blurred vision",
    "dizziness_eyes_open": "Dizziness (eyes open)",
    "dizziness_eyes_closed": "Dizziness (eyes closed)",
    "vertigo": "Vertigo",
    "stomach_awareness": "Stomach awareness",
    "burping": "Burping",
}

# Standard Kennedy et al. SSQ component memberships.
NAUSEA_KEYS = [
    "general_discomfort", "increased_salivation", "sweating", "nausea",
    "difficulty_concentrating", "stomach_awareness", "burping",
]
OCULOMOTOR_KEYS = [
    "general_discomfort", "fatigue", "headache", "eyestrain",
    "difficulty_focusing", "difficulty_concentrating", "blurred_vision",
]
DISORIENTATION_KEYS = [
    "difficulty_focusing", "nausea", "fullness_head", "blurred_vision",
    "dizziness_eyes_open", "dizziness_eyes_closed", "vertigo",
]


def _require_columns(df: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    missing = [column for column in columns if column not in df.columns]
    if missing:
        raise ValueError(f"{label} is missing required columns: {missing}")


def prepare_downlink_packets(traffic: pd.DataFrame, cfg: AnalysisConfig) -> pd.DataFrame:
    _require_columns(traffic, ["time", "size", "direction"], "Traffic CSV")
    dl = traffic.loc[traffic["direction"].astype(str).str.upper() == "DL"].copy()
    if dl.empty:
        raise ValueError("Traffic CSV contains no downlink (DL) packets.")
    dl["time"] = pd.to_numeric(dl["time"], errors="coerce")
    dl["size"] = pd.to_numeric(dl["size"], errors="coerce") - cfg.header_size_bytes
    dl = dl.dropna(subset=["time", "size"])
    dl = dl.loc[dl["size"] > cfg.size_threshold_bytes].sort_values("time").reset_index(drop=True)
    if dl.empty:
        raise ValueError("No DL packets remain after the packet-size threshold.")
    dl["time"] -= dl["time"].iloc[0]
    return dl


def extract_raw_frames(dl: pd.DataFrame, cfg: AnalysisConfig) -> pd.DataFrame:
    times = dl["time"].to_numpy(dtype=float)
    group_ids = np.r_[0, np.cumsum(np.diff(times) >= cfg.packet_gap_threshold_s)]
    work = dl.assign(frame_id=group_ids)
    raw = (
        work.groupby("frame_id", sort=True)
        .agg(frame_time=("time", "min"), frame_size=("size", "sum"), num_pkts=("size", "size"))
        .reset_index(drop=True)
    )
    raw["raw_IFI"] = raw["frame_time"].diff().fillna(cfg.theoretical_ifi_s)
    return raw


def build_filled_timeline(raw: pd.DataFrame, cfg: AnalysisConfig) -> pd.DataFrame:
    rows: list[dict] = []
    ideal = cfg.theoretical_ifi_s
    for i, row in raw.iterrows():
        if i > 0:
            previous_time = float(raw.loc[i - 1, "frame_time"])
            current_time = float(row["frame_time"])
            gap = current_time - previous_time
            missing = max(0, int(round(gap / ideal)) - 1) if gap > 1.5 * ideal else 0
            for j in range(1, missing + 1):
                rows.append({
                    "frame_time": previous_time + j * ideal,
                    "frame_size": 0.0,
                    "num_pkts": 0,
                    "skipped_frame": True,
                    "raw_IFI": gap,
                })
        rows.append({
            "frame_time": float(row["frame_time"]),
            "frame_size": float(row["frame_size"]),
            "num_pkts": int(row["num_pkts"]),
            "skipped_frame": False,
            "raw_IFI": float(row["raw_IFI"]),
        })

    frames = pd.DataFrame(rows).sort_values("frame_time").reset_index(drop=True)
    frames.insert(0, "frame_idx", np.arange(len(frames)))
    frames["IFI"] = frames["frame_time"].diff().fillna(ideal)
    frames["long_gap"] = frames["raw_IFI"] > cfg.long_gap_factor * ideal
    frames["high_var"] = (frames["IFI"] - ideal).abs() > cfg.high_variation_s
    frames["network_risk"] = frames[["skipped_frame", "long_gap", "high_var"]].any(axis=1)
    return frames


def align_motion(raw: pd.DataFrame, movement: pd.DataFrame, cfg: AnalysisConfig) -> pd.DataFrame:
    required = ["time", "HeadPosX", "HeadPosY", "HeadPosZ"]
    _require_columns(movement, required, "Movement CSV")
    mv = movement[required].copy()
    for column in required:
        mv[column] = pd.to_numeric(mv[column], errors="coerce")
    mv = mv.dropna().sort_values("time").reset_index(drop=True)
    if mv.empty:
        raise ValueError("Movement CSV has no valid rows.")
    mv["motion_time"] = mv["time"] - mv["time"].iloc[0]

    aligned = pd.merge_asof(
        raw.sort_values("frame_time"),
        mv[["motion_time", "HeadPosX", "HeadPosY", "HeadPosZ"]],
        left_on="frame_time",
        right_on="motion_time",
        direction="nearest",
    )
    # Signed offset: positive means the selected movement sample occurs after the frame.
    aligned["delta_offset_s"] = aligned["motion_time"] - aligned["frame_time"]
    aligned["delta_offset_ms"] = aligned["delta_offset_s"] * 1000.0
    aligned["abs_delta_offset_ms"] = aligned["delta_offset_ms"].abs()
    aligned["motion_misaligned"] = aligned["abs_delta_offset_ms"] > cfg.alignment_tolerance_s * 1000.0
    return aligned


def compute_ssq_scores(ssq: pd.DataFrame) -> pd.DataFrame:
    id_col = "ID"
    q_col = "Questionnaire number" if "Questionnaire number" in ssq.columns else "Questionnaire_number"
    _require_columns(ssq, [id_col, q_col, *SSQ_COLUMNS.values()], "SSQ CSV")

    work = ssq.copy()
    scale = {"none": 0, "slight": 1, "moderate": 2, "severe": 3}
    for column in SSQ_COLUMNS.values():
        if not pd.api.types.is_numeric_dtype(work[column]):
            work[column] = work[column].astype(str).str.strip().str.lower().map(scale)
        work[column] = pd.to_numeric(work[column], errors="coerce")
    if work[list(SSQ_COLUMNS.values())].isna().any().any():
        raise ValueError("SSQ CSV contains unknown or missing symptom ratings.")

    def sum_keys(keys: list[str]) -> pd.Series:
        return work[[SSQ_COLUMNS[key] for key in keys]].sum(axis=1)

    work["SSQ_Nausea"] = 9.54 * sum_keys(NAUSEA_KEYS)
    work["SSQ_Oculomotor"] = 7.58 * sum_keys(OCULOMOTOR_KEYS)
    work["SSQ_Disorientation"] = 13.92 * sum_keys(DISORIENTATION_KEYS)
    work["SSQ_Total"] = 3.74 * work[list(SSQ_COLUMNS.values())].sum(axis=1)
    return work[[id_col, q_col, "SSQ_Nausea", "SSQ_Oculomotor", "SSQ_Disorientation", "SSQ_Total"]]


def session_ssq_delta(scores: pd.DataFrame, user_id: str, game_speed: str) -> dict[str, float]:
    q_col = "Questionnaire number" if "Questionnaire number" in scores.columns else "Questionnaire_number"
    user = scores.loc[scores["ID"] == user_id].sort_values(q_col)
    if user.empty:
        return {"ssq_pre": np.nan, "ssq_post": np.nan, "ssq_delta": np.nan}
    by_q = user.set_index(q_col)["SSQ_Total"]
    match = re.search(r"_order(\d+)_", user_id)
    if not match:
        return {"ssq_pre": np.nan, "ssq_post": np.nan, "ssq_delta": np.nan}
    order = int(match.group(1))
    # Dataset definition: order 1 = slow first; order 2 = slow second (fast first).
    first_speed = "slow" if order == 1 else "fast"
    if game_speed == first_speed:
        pre_q, post_q = 1, 2
    else:
        pre_q, post_q = 3, 4
    if pre_q not in by_q.index or post_q not in by_q.index:
        return {"ssq_pre": np.nan, "ssq_post": np.nan, "ssq_delta": np.nan}
    pre, post = float(by_q.loc[pre_q]), float(by_q.loc[post_q])
    return {"ssq_pre": pre, "ssq_post": post, "ssq_delta": post - pre}


def analyze_session(
    traffic_path: Path,
    movement_path: Path,
    user_id: str,
    game_speed: str,
    cfg: AnalysisConfig,
    ssq_scores: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict[str, float | str | int]]:
    traffic = pd.read_csv(traffic_path)
    movement = pd.read_csv(movement_path)
    dl = prepare_downlink_packets(traffic, cfg)
    raw = extract_raw_frames(dl, cfg)
    frames = build_filled_timeline(raw, cfg)
    raw_alignment = align_motion(raw, movement, cfg)
    frames = pd.merge_asof(
        frames.sort_values("frame_time"),
        raw_alignment[["frame_time", "motion_time", "HeadPosX", "HeadPosY", "HeadPosZ",
                       "delta_offset_s", "delta_offset_ms", "abs_delta_offset_ms", "motion_misaligned"]],
        on="frame_time",
        direction="nearest",
    )
    frames["risk_flag"] = (frames["network_risk"] | frames["motion_misaligned"]).astype(int)

    movement = movement.sort_values("time").copy()
    xyz = movement[["HeadPosX", "HeadPosY", "HeadPosZ"]].apply(pd.to_numeric, errors="coerce").to_numpy()
    mt = pd.to_numeric(movement["time"], errors="coerce").to_numpy()
    dt = np.diff(mt)
    distance = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
    valid = np.isfinite(dt) & (dt > 0) & np.isfinite(distance)
    speed = distance[valid] / dt[valid]

    duration = float(dl["time"].iloc[-1] - dl["time"].iloc[0])
    packet_intervals = np.diff(dl["time"].to_numpy())
    summary: dict[str, float | str | int] = {
        "user_id": user_id,
        "game_speed": game_speed,
        "traffic_file": str(traffic_path),
        "movement_file": str(movement_path),
        "duration_s": duration,
        "mean_packet_interval_ms": float(np.mean(packet_intervals) * 1000),
        "packet_interval_jitter_ms": float(np.std(packet_intervals, ddof=1) * 1000) if len(packet_intervals) > 1 else 0.0,
        "bitrate_mbps": float(dl["size"].sum() * 8 / duration / 1e6) if duration > 0 else np.nan,
        "motion_intensity_mps": float(np.mean(speed)) if len(speed) else np.nan,
        "num_frames": int(len(frames)),
        "num_skipped_frames": int(frames["skipped_frame"].sum()),
        "num_risk_frames": int(frames["risk_flag"].sum()),
        "mean_abs_delta_offset_ms": float(frames["abs_delta_offset_ms"].mean()),
        "p95_abs_delta_offset_ms": float(frames["abs_delta_offset_ms"].quantile(0.95)),
        "max_abs_delta_offset_ms": float(frames["abs_delta_offset_ms"].max()),
        "misaligned_frame_ratio": float(frames["motion_misaligned"].mean()),
    }
    if ssq_scores is not None:
        summary.update(session_ssq_delta(ssq_scores, user_id, game_speed))
    return frames, summary
