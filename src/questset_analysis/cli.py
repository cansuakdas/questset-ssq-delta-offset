from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd

from .core import AnalysisConfig, analyze_session, compute_ssq_scores


def discover_sessions(data_root: Path):
    for traffic in sorted(data_root.rglob("*_traffic.csv")):
        match = re.match(r"(.+)_(fast|slow)_traffic\.csv$", traffic.name)
        if not match:
            continue
        user_id, speed = match.groups()
        movement = traffic.with_name(f"{user_id}_{speed}_movement.csv")
        if movement.exists():
            yield user_id, speed, traffic, movement


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze open Questset traffic, movement and SSQ data.")
    parser.add_argument("--data-root", type=Path, required=True, help="Questset Complete/Incomplete data root.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--ssq-file", type=Path, help="Path to SSQ.csv. If omitted, recursively searched.")
    parser.add_argument("--no-frame-files", action="store_true", help="Only write the session summary CSV.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    ssq_path = args.ssq_file
    if ssq_path is None:
        candidates = list(args.data_root.rglob("SSQ.csv"))
        ssq_path = candidates[0] if candidates else None
    ssq_scores = compute_ssq_scores(pd.read_csv(ssq_path)) if ssq_path else None

    cfg = AnalysisConfig()
    summaries = []
    failures = []
    for user_id, speed, traffic, movement in discover_sessions(args.data_root):
        try:
            frames, summary = analyze_session(traffic, movement, user_id, speed, cfg, ssq_scores)
            summaries.append(summary)
            if not args.no_frame_files:
                frames.to_csv(args.output_dir / f"{user_id}_{speed}_frames_with_flags.csv", index=False)
            print(f"[OK] {user_id} / {speed}")
        except Exception as exc:  # continue batch processing while recording failures
            failures.append(f"{traffic}: {exc}")
            print(f"[FAIL] {traffic.name}: {exc}")

    pd.DataFrame(summaries).to_csv(args.output_dir / "session_summary.csv", index=False)
    if failures:
        (args.output_dir / "failures.txt").write_text("\n".join(failures), encoding="utf-8")
    print(f"Saved outputs to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
