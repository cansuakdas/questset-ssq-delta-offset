import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List

# ===================== PATHS =====================
BASE_DIR = Path.home() / "Desktop" / "Questset" / "Incomplete data"
OUT_DIR  = Path.home() / "Desktop" / "Questset" / "Incomplete_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ===================== PARAMETERS =====================
HEADER_SIZE          = 27
SIZE_THRESHOLD_BYTES = 5 * 1024
DL_LABEL             = "DL"

THEORETICAL_FPS = 72.0
THEORETICAL_IFI = 1.0 / THEORETICAL_FPS
PKT_GAP_THRESHOLD = 0.005

LONG_GAP_FACTOR  = 3.0
HIGH_VAR_ABS     = 0.01
ALIGN_TOLERANCE  = 0.005


# ===================== HELPERS =====================
def find_file(folder: Path, suffix: str) -> Optional[Path]:
    matches = list(folder.glob(f"*{suffix}"))
    return matches[0] if matches else None


def extract_raw_frames(dl: pd.DataFrame) -> pd.DataFrame:
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


def build_filled_timeline(raw_frames: pd.DataFrame) -> pd.DataFrame:
    filled_times, filled_sizes, filled_pkts, skipped_flags, raw_IFIs = [], [], [], [], []

    prev_t       = raw_frames["frame_time"].iloc[0]
    prev_s       = raw_frames["frame_size"].iloc[0]
    prev_n       = raw_frames["num_pkts"].iloc[0]
    prev_raw_IFI = raw_frames["raw_IFI"].iloc[0]

    filled_times.append(prev_t)
    filled_sizes.append(prev_s)
    filled_pkts.append(prev_n)
    skipped_flags.append(False)
    raw_IFIs.append(prev_raw_IFI)

    for _, row in raw_frames.iloc[1:].iterrows():
        t, s, n, rifi = row["frame_time"], row["frame_size"], row["num_pkts"], row["raw_IFI"]
        gap = t - prev_t

        if gap > 1.5 * THEORETICAL_IFI:
            missing = int(round(gap / THEORETICAL_IFI)) - 1
            for _ in range(max(0, missing)):
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

    frames["IFI"] = frames["frame_time"].diff()
    frames.loc[0, "IFI"] = THEORETICAL_IFI

    frames["long_gap"] = frames["raw_IFI"] > (LONG_GAP_FACTOR * THEORETICAL_IFI)
    frames["high_var"] = (frames["IFI"] - THEORETICAL_IFI).abs() > HIGH_VAR_ABS
    frames["skipped_risk"] = frames["skipped_frame"]
    frames["network_risk"] = frames["long_gap"] | frames["high_var"] | frames["skipped_risk"]

    return frames


def compute_raw_motion_alignment(raw_frames: pd.DataFrame, move: pd.DataFrame) -> pd.DataFrame:
    mv = move.sort_values("time").copy()
    mv["t_rel"] = mv["time"] - mv["time"].iloc[0]

    rf = raw_frames.sort_values("frame_time").reset_index(drop=True)

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


def process_user(traffic_path: Path, movement_path: Path, user_id: str) -> pd.DataFrame:
    traffic = pd.read_csv(traffic_path)
    dl = traffic[traffic["direction"] == DL_LABEL].copy()

    dl["size"] = dl["size"] - HEADER_SIZE
    dl = dl[dl["size"] > SIZE_THRESHOLD_BYTES].copy()
    dl["time"] = dl["time"] - dl["time"].iloc[0]

    raw_frames = extract_raw_frames(dl)
    frames = build_filled_timeline(raw_frames)

    move = pd.read_csv(movement_path)
    move["time"] = move["time"] - move["time"].iloc[0]

    raw_align = compute_raw_motion_alignment(raw_frames, move)

    frames = pd.merge_asof(
        frames.sort_values("frame_time"),
        raw_align[["frame_time", "HeadPosX", "HeadPosY", "HeadPosZ",
                   "motion_dt", "motion_misaligned"]],
        on="frame_time",
        direction="nearest"
    )

    frames["risk_flag"] = (frames["network_risk"] | frames["motion_misaligned"]).astype(int)
    return frames


# ===================== MAIN =====================
def main():
    user_folders = [p for p in BASE_DIR.iterdir() if p.is_dir()]
    failures: List[str] = []

    for uf in sorted(user_folders):
        user_id = uf.name
        traffic_path  = find_file(uf, "_fast_traffic.csv")
        movement_path = find_file(uf, "_fast_movement.csv")

        if traffic_path is None or movement_path is None:
            failures.append(f"{user_id}: missing traffic or movement file")
            continue

        try:
            frames = process_user(traffic_path, movement_path, user_id)
            out_file = OUT_DIR / f"{user_id}_fast_frames_with_flags.csv"
            frames.to_csv(out_file, index=False)
            print(f"[OK] {user_id} → {out_file.name}")

        except Exception as e:
            failures.append(f"{user_id}: {repr(e)}")

    if failures:
        fail_log = OUT_DIR / "failures.txt"
        fail_log.write_text("\n".join(failures), encoding="utf-8")
        print(f"\nSome users failed. See {fail_log}")


if __name__ == "__main__":
    main()
