import pandas as pd
import numpy as np
from pathlib import Path

# ===================== USER SETTINGS =====================

USER = "group1_order1_user10"

DATA_DIR = Path(".")
SSQ_FILE = Path("SSQ.csv")

TRAFFIC_FILE  = DATA_DIR / f"{USER}_fast_traffic.csv"
MOVEMENT_FILE = DATA_DIR / f"{USER}_fast_movement.csv"

# Packet / frame parameters
HEADER_SIZE          = 27          # USBPcap header
SIZE_THRESHOLD_BYTES = 5 * 1024    # keep packets > 5 kB
DL_LABEL             = "DL"        # downlink label

THEORETICAL_FPS = 72.0
THEORETICAL_IFI = 1.0 / THEORETICAL_FPS   # ≈ 0.0139 s
PKT_GAP_THRESHOLD = 0.005                 # 5 ms → same frame

# Thresholds (can be tuned)
LONG_GAP_FACTOR  = 3.0     # raw_IFI > 3 * ideal IFI → long gap (~42 ms)
HIGH_VAR_ABS     = 0.01    # |IFI − ideal| > 10 ms  → high jitter
ALIGN_TOLERANCE  = 0.005   # > 5 ms → motion misaligned (tighter than before)

MOTION_RATE_HZ = 60.0
MOTION_PERIOD  = 1.0 / MOTION_RATE_HZ


# =========================================================
# 1) Cluster DL packets → RAW FRAMES
# =========================================================

def extract_raw_frames(dl: pd.DataFrame) -> pd.DataFrame:
    """
    From DL packets:
    - normalize time (t_rel)
    - cluster packets into frames using PKT_GAP_THRESHOLD
    - compute raw frame_time (first packet)
    - compute raw_IFI between raw frames
    """

    dl = dl.sort_values("time").copy()
    dl["t_rel"] = dl["time"] - dl["time"].iloc[0]

    times = dl["t_rel"].values
    ipi   = np.diff(times)

    pkt_grp = [0]
    grp = 0
    for dt in ipi:
        if dt < PKT_GAP_THRESHOLD:
            pkt_grp.append(grp)
        else:
            grp += 1
            pkt_grp.append(grp)

    dl["frame_id"] = pkt_grp

    raw_frames = (
        dl.groupby("frame_id")
          .agg(frame_time=("t_rel", "min"),
               frame_size=("size", "sum"),
               num_pkts=("size", "count"))
          .reset_index(drop=True)
    )

    raw_frames["raw_IFI"] = raw_frames["frame_time"].diff()
    raw_frames.loc[0, "raw_IFI"] = THEORETICAL_IFI

    return raw_frames


# =========================================================
# 2) Build zero-filled frame timeline (for jitter etc.)
# =========================================================

def build_filled_timeline(raw_frames: pd.DataFrame) -> pd.DataFrame:
    """
    Expand raw_frames into a filled timeline:
    - insert zero-size frames when there are big gaps
    - keep raw_IFI info for each filled frame
    """

    filled_times  = []
    filled_sizes  = []
    filled_pkts   = []
    skipped_flags = []
    raw_IFIs      = []

    prev_t       = raw_frames["frame_time"].iloc[0]
    prev_s       = raw_frames["frame_size"].iloc[0]
    prev_n       = raw_frames["num_pkts"].iloc[0]
    prev_raw_IFI = raw_frames["raw_IFI"].iloc[0]

    filled_times.append(prev_t)
    filled_sizes.append(prev_s)
    filled_pkts.append(prev_n)
    skipped_flags.append(False)
    raw_IFIs.append(prev_raw_IFI)

    for t, s, n, rifi in raw_frames.iloc[1:].itertuples(index=False):
        gap = t - prev_t

        # insert missing frames if gap is too large
        if gap > 1.5 * THEORETICAL_IFI:
            missing = int(round(gap / THEORETICAL_IFI)) - 1
            for _ in range(missing):
                prev_t += THEORETICAL_IFI
                filled_times.append(prev_t)
                filled_sizes.append(0.0)
                filled_pkts.append(0)
                skipped_flags.append(True)
                raw_IFIs.append(gap)

        filled_times.append(t)
        filled_sizes.append(s)
        filled_pkts.append(n)
        skipped_flags.append(False)
        raw_IFIs.append(rifi)

        prev_t = t

    frames = pd.DataFrame({
        "frame_idx": range(len(filled_times)),
        "frame_time": filled_times,
        "frame_size": filled_sizes,
        "num_pkts": filled_pkts,
        "skipped_frame": skipped_flags,
        "raw_IFI": raw_IFIs
    })

    # filled IFI
    frames["IFI"] = frames["frame_time"].diff()
    frames.loc[0, "IFI"] = THEORETICAL_IFI

    # network-side flags
    frames["long_gap"] = frames["raw_IFI"] > (LONG_GAP_FACTOR * THEORETICAL_IFI)
    frames["high_var"] = (frames["IFI"] - THEORETICAL_IFI).abs() > HIGH_VAR_ABS
    frames["skipped_risk"] = frames["skipped_frame"]
    frames["network_risk"] = (
        frames["long_gap"] |
        frames["high_var"] |
        frames["skipped_risk"]
    )

    return frames


# =========================================================
# 3) RAW FRAMES → MOTION ALIGNMENT (real misalignment)
# =========================================================

def compute_raw_motion_alignment(raw_frames: pd.DataFrame,
                                 move: pd.DataFrame) -> pd.DataFrame:
    """
    Compute motion_dt from RAW frame times (no zero-fill):
    motion_dt = |frame_time_raw - nearest_motion_time|
    """

    mv = move.sort_values("time").copy()
    mv["t_rel"] = mv["time"] - mv["time"].iloc[0]

    rf = raw_frames.copy()
    rf = rf.sort_values("frame_time").reset_index().rename(columns={"index": "raw_frame_idx"})

    aligned = pd.merge_asof(
        rf,
        mv.rename(columns={"t_rel": "t_motion"})[
            ["t_motion", "HeadPosX", "HeadPosY", "HeadPosZ"]
        ],
        left_on="frame_time",
        right_on="t_motion",
        direction="nearest"
    )

    aligned["motion_dt"] = (aligned["frame_time"] - aligned["t_motion"]).abs()
    aligned["motion_misaligned"] = aligned["motion_dt"] > ALIGN_TOLERANCE

    return aligned


# =========================================================
# 4) SSQ
# =========================================================

def compute_ssq_total(ssq_file: Path, user_id: str) -> float:
    ssq = pd.read_csv(ssq_file)
    ssq_u = ssq[ssq["ID"] == user_id].copy()
    if ssq_u.empty:
        return float("nan")

    scale = {"None": 0, "Slight": 1, "Moderate": 2, "Severe": 3}
    symptom_cols = [
        "General discomfort","Fatigue","Headache","Eyestrain","Difficulty focusing",
        "Increased salivation","Nausea","Difficulty concentrating","Fullness of the head",
        "Blurred vision","Dizziness (eyes closed)","Dizziness (eyes open)","Vertigo",
        "Stomach awareness","Burping","Sweating"
    ]
    for c in symptom_cols:
        if c in ssq_u.columns and ssq_u[c].dtype == object:
            ssq_u[c] = ssq_u[c].map(scale)

    N = ssq_u[["Nausea","Stomach awareness","Burping","Sweating"]].sum(axis=1)
    O = ssq_u[["General discomfort","Fatigue","Headache","Eyestrain",
               "Difficulty focusing","Blurred vision","Difficulty concentrating"]].sum(axis=1)
    D = ssq_u[["Fullness of the head","Dizziness (eyes open)",
               "Dizziness (eyes closed)","Vertigo"]].sum(axis=1)

    ssq_u["SSQ_Total"] = 9.54*N + 7.58*O + 13.92*D
    q_col = "Questionnaire number" if "Questionnaire number" in ssq_u.columns else "Questionnaire_number"
    return float(ssq_u.sort_values(q_col).iloc[-1]["SSQ_Total"])


# =========================================================
# MAIN
# =========================================================

def main():
    # ---------- read traffic ----------
    traffic = pd.read_csv(TRAFFIC_FILE)
    dl = traffic[traffic["direction"] == DL_LABEL].copy()
    dl["size"] = dl["size"] - HEADER_SIZE
    dl = dl[dl["size"] > SIZE_THRESHOLD_BYTES].copy()

    # normalize time
    dl["time"] = dl["time"] - dl["time"].iloc[0]

    # RAW FRAMES
    raw_frames = extract_raw_frames(dl)

    # FILLED TIMELINE + NETWORK FLAGS
    frames = build_filled_timeline(raw_frames)

    # ---------- read movement ----------
    move = pd.read_csv(MOVEMENT_FILE)
    move["time"] = move["time"] - move["time"].iloc[0]

    # MOTION ALIGNMENT ON RAW FRAMES
    raw_align = compute_raw_motion_alignment(raw_frames, move)

    # map motion alignment info onto filled frames (nearest frame_time)
    frames = pd.merge_asof(
        frames.sort_values("frame_time"),
        raw_align[["frame_time", "HeadPosX", "HeadPosY", "HeadPosZ",
                   "motion_dt", "motion_misaligned"]],
        on="frame_time",
        direction="nearest"
    )

    # FINAL risk_flag = network_risk OR motion_misaligned
    frames["risk_flag"] = (frames["network_risk"] | frames["motion_misaligned"]).astype(int)

    # ---------- scalar metrics ----------
    dt = dl["time"].diff().dropna().to_numpy()
    latency_ms = dt.mean()*1e3
    jitter_ms  = dt.std()*1e3
    bitrate_mbps = (dl["size"].sum()*8)/(dl["time"].iloc[-1]) / 1e6

    dx = np.diff(move["HeadPosX"])
    dy = np.diff(move["HeadPosY"])
    dz = np.diff(move["HeadPosZ"])
    dtm = np.diff(move["time"])
    speed = np.sqrt(dx**2 + dy**2 + dz**2) / dtm
    motion_intensity = np.nanmean(speed)

    ssq_total = compute_ssq_total(SSQ_FILE, USER)

    # ---------- print summary ----------
    print("===== SUMMARY =====")
    print("User:", USER)
    print(f"Latency_ms: {latency_ms:.3f}")
    print(f"Jitter_ms : {jitter_ms:.3f}")
    print(f"Bitrate_Mbps: {bitrate_mbps:.3f}")
    print(f"MotionIntensity_mps: {motion_intensity:.4f}")
    print(f"SSQ_Total: {ssq_total:.2f}")
    print(f"NumFrames: {len(frames)}")
    print(f"NumNetworkRisk: {frames['network_risk'].sum()}")
    print(f"NumMotionMisaligned: {frames['motion_misaligned'].sum()}")
    print(f"NumRiskFrames: {frames['risk_flag'].sum()}")

    out_name = f"{USER}_fast_frames_with_flags.csv"
    frames.to_csv(out_name, index=False)
    print("Saved:", out_name)


if __name__ == "__main__":
    main()
