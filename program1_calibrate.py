#!/usr/bin/env python3
"""
program1_calibrate.py — CLI entry point for Program 1 (Calibration).

Reads a colour reference chart image + ROI config, builds a
CalibrationModel, and saves it to a JSON file.

Usage
-----
    python program1_calibrate.py \\
        --chart tests/fixtures/chart.png \\
        --rois  config/chart_rois.json   \\
        --output models/model.json
"""
import argparse
import sys

from api.calibrator_api import build_model, build_model_from_colors, save_model


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a urinalysis strip calibration model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # From image + ROI coords:\n"
            "  python program1_calibrate.py --chart chart.png --rois config/chart_rois.json\n\n"
            "  # From direct RGB values (e.g. read with Digital Color Meter):\n"
            "  python program1_calibrate.py --colors config/chart_colors.json\n"
        ),
    )
    parser.add_argument(
        "--colors",
        default=None,
        metavar="PATH",
        help="Path to chart_colors.json with direct RGB values (no image needed).",
    )
    parser.add_argument(
        "--chart",
        default=None,
        metavar="PATH",
        help="Path to the reference colour chart image (PNG/JPG).",
    )
    parser.add_argument(
        "--rois",
        default="config/chart_rois.json",
        metavar="PATH",
        help="Path to chart_rois.json — only used with --chart (default: config/chart_rois.json).",
    )
    parser.add_argument(
        "--output",
        default="models/model.json",
        metavar="PATH",
        help="Output path for the calibration model JSON (default: models/model.json).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.colors:
        print(f"[Program 1] Building model from RGB config: {args.colors}")
        try:
            model = build_model_from_colors(args.colors)
        except (FileNotFoundError, ValueError) as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
    elif args.chart:
        print(f"[Program 1] Building model from chart image: {args.chart}")
        print(f"            ROI config: {args.rois}")
        try:
            model = build_model(args.chart, args.rois)
        except (FileNotFoundError, ValueError) as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("[ERROR] Provide either --colors <path> or --chart <path>", file=sys.stderr)
        sys.exit(1)

    save_model(model, args.output)
    print(f"\n✅  Calibration complete. Model saved to: {args.output}")
    print(f"    Analytes calibrated: {', '.join(model.analyte_names())}")


if __name__ == "__main__":
    main()
