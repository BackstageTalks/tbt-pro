"""Run offline BlinQ/721 study on verified local Sackmann-compatible exports."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
from .pre_match import build_features
from .evaluate import walk_forward


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline BlinQ 721 research; no CDB writes or live model changes")
    parser.add_argument("--tour", required=True, choices=["ATP", "WTA"])
    parser.add_argument("--input", action="append", required=True, type=Path,
                        help="Sackmann-compatible CSV; repeat for multiple files")
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    files = sorted(set(args.input))
    for p in files:
        if not p.is_file():
            parser.error(f"Input not found: {p}")
    def source():
        for path in files:
            with path.open("r",encoding="utf-8-sig",newline="") as handle:
                yield from csv.DictReader(handle)
    rows, rejected = build_features(source(),args.tour)
    report = walk_forward(rows)
    report["dataset"] = {"tour":args.tour,"input_files":list(map(str,files)),
                         "reconstructed_match_ids":sum("|AUTO:" in r["match_id"] for r in rows),
                         "accepted":len(rows),"rejected":len(rejected),
                         "match_date_precision":"tournament_start_plus_21_day_embargo",
                         "identity":"tour_and_provider_player_id_required"}
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir/"research_report.json").write_text(json.dumps(report,indent=2,sort_keys=True),encoding="utf-8")
    (args.out_dir/"rejected.json").write_text(json.dumps(rejected,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps({"accepted":len(rows),"rejected":len(rejected),
                      "folds":report["evaluated_years"],
                      "report_path":str(args.out_dir/"research_report.json")},sort_keys=True))


if __name__=="__main__":
    main()
