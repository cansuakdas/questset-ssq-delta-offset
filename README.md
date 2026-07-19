# Questset SSQ and Delta-Offset Analysis

This repository provides a reproducible starting-point analysis for the publicly available **Questset** virtual-reality dataset. It processes traffic, motion, and Simulator Sickness Questionnaire (SSQ) files. The dataset itself is not included; only analysis code is distributed.

## What this repository adds

The pipeline follows the traffic-processing approach described for Questset: it removes the 27-byte USBPcap pseudo-header, keeps downlink packets larger than 5 kB, groups packets separated by less than 5 ms into the same video frame, and inserts zero-size frames when frames are missing from the expected 72 FPS timeline.

The repository adds the following analyses:

1. **Standard SSQ scores:** Nausea, Oculomotor, Disorientation, and Total scores are calculated using the standard Kennedy SSQ weighting factors.
2. **Session-specific SSQ change (`ssq_delta`):** The score immediately before a game is subtracted from the score immediately after that game. Questset order information is interpreted automatically (`order1`: slow game first; `order2`: fast game first).
3. **Traffic-to-motion delta offset:** Each raw video frame is matched to the nearest motion sample. The signed offset is defined as `delta_offset_ms = motion_time - frame_time`. Positive values indicate that the nearest motion sample occurred after the frame timestamp. Absolute offset and the proportion above a 5 ms alignment tolerance are also reported.
4. **Frame-level risk flags:** Frames are marked when they contain a skipped frame, a long inter-frame gap, high inter-frame variation, or a motion-alignment mismatch.

> **Important:** `mean_packet_interval_ms` is not end-to-end network latency. It is the mean time interval between selected downlink packets.

## Dataset

Questset contains more than 40 hours of VR traffic, HMD/controller motion, and SSQ data collected from 70 participants.

- Dataset: https://researchdata.cab.unipd.it/1179/
- Official Questset API: https://github.com/signetlabdei/questset
- Paper DOI: https://doi.org/10.1145/3625468.3652187

Download the dataset separately and organize it, for example, as follows:

```text
data/
├── Complete data/
│   ├── SSQ.csv
│   └── group1_order1_user0/
│       ├── group1_order1_user0_fast_traffic.csv
│       ├── group1_order1_user0_fast_movement.csv
│       ├── group1_order1_user0_slow_traffic.csv
│       └── group1_order1_user0_slow_movement.csv
└── Incomplete data/
```

## Repository structure

```text
.
├── src/questset_analysis/   # Main reusable analysis package
├── scripts/                 # Small entry-point scripts
├── tests/                   # Automated tests
├── legacy/                  # Earlier prototype scripts kept for reference
├── data/                    # Dataset location; real data are ignored by Git
├── outputs/                 # Generated outputs; ignored except for .gitkeep
├── README.md
├── GITHUB_UPLOAD_GUIDE.md
├── pyproject.toml
├── requirements.txt
└── LICENSE
```

## Installation

```bash
cd questset-ssq-delta-offset
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -e .
```

## Usage

Analyze the complete dataset:

```bash
questset-analyze \
  --data-root "data/Complete data" \
  --output-dir "outputs/complete"
```

Analyze the incomplete dataset:

```bash
questset-analyze \
  --data-root "data/Incomplete data" \
  --output-dir "outputs/incomplete"
```

Generate only the session summary without writing large frame-level CSV files:

```bash
questset-analyze \
  --data-root "data/Complete data" \
  --output-dir "outputs/complete" \
  --no-frame-files
```

## Outputs

`session_summary.csv` contains one row per participant and game condition, including:

- bitrate, packet-interval, and jitter summaries
- mean HMD motion intensity
- skipped-frame and risk-frame counts
- mean, 95th-percentile, and maximum absolute delta offset
- motion-misalignment proportion
- `ssq_pre`, `ssq_post`, and `ssq_delta`

Each `*_frames_with_flags.csv` file contains frame-level variables such as:

- `delta_offset_ms`
- `abs_delta_offset_ms`
- `skipped_frame`
- `long_gap`
- `high_var`
- `motion_misaligned`
- `risk_flag`

## Methodological assumptions

- Traffic and motion timestamps are reset relative to the first sample in each file. Delta offset therefore measures within-session relative alignment rather than alignment to a shared absolute clock.
- Nearest-neighbor motion matching is used. The resulting delta offset is not a causal motion-to-photon latency measurement.
- The 5 ms packet-clustering threshold and 72 FPS frame rate follow the published Questset processing approach.
- The 5 ms motion-alignment tolerance and risk thresholds are starting values for analysis. A sensitivity analysis is recommended before reporting research conclusions.

## Tests

Run the tests with:

```bash
python -m pytest
```

## Citation

Please cite the original Questset publication and dataset when using this repository:

```bibtex
@inproceedings{baldoni2024questset,
  title={Questset: A VR Dataset for Network and Quality of Experience Studies},
  author={Baldoni, Sara and Battisti, Federica and Chiariotti, Federico and others},
  booktitle={ACM Multimedia Systems Conference},
  year={2024},
  doi={10.1145/3625468.3652187}
}
```

## License

The analysis code in this repository is released under the MIT License. The Questset dataset and original Questset code remain subject to their own licensing and citation requirements. Do not upload participant data or large generated output files to this repository.
