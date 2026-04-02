#!/usr/bin/env python3
"""
program2_analyze.py — CLI entry point for Program 2 (Strip Analysis).

Crops the strip from a CV-system output image, segments reagent boxes,
and reports concentrations using a calibration model.

Usage
-----
    python program2_analyze.py \\
        --image  strip.png             \\
        --model  models/model.json     \\
        --config config/strip_config.json \\
        [--manual-pad-h 48 --manual-gap-h 20 --manual-y-offset 60] \\
        [--output results.json]        \\
        [--debug]
"""
import argparse
import sys
from pathlib import Path

from api.analyzer_api import results_to_json
from core.calibration import CalibrationModel
from core.strip_analyzer import StripAnalyzer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyse a urinalysis strip image and report concentrations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--image",
        required=True,
        metavar="PATH",
        help="Path to the CV-system output image (strip with coloured border).",
    )
    parser.add_argument(
        "--model",
        default="models/model.json",
        metavar="PATH",
        help="Path to the calibration model JSON (default: models/model.json).",
    )
    parser.add_argument(
        "--config",
        default="config/strip_config.json",
        metavar="PATH",
        help="Path to strip_config.json (default: config/strip_config.json).",
    )
    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Optional: save results JSON to this path.",
    )
    
    # --- Manual Config Overrides ---
    parser.add_argument(
        "--manual-pad-h",
        type=int,
        default=None,
        help="Override the automatic template search with an explicit pad height in pixels.",
    )
    parser.add_argument(
        "--manual-gap-h",
        type=int,
        default=None,
        help="Override the automatic template search with an explicit gap height in pixels.",
    )
    parser.add_argument(
        "--manual-y-offset",
        type=int,
        default=None,
        help="Override the automatic template search with an explicit top margin in pixels.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=(
            "Save an annotated debug image showing identified boxes, sampled "
            "colours, analyte labels, values, and confidence scores. "
            "Output is written to <image_stem>_debug.png by default."
        ),
    )
    parser.add_argument(
        "--debug-output",
        default=None,
        metavar="PATH",
        help="Path for the debug image (default: <image_stem>_debug.png).",
    )
    parser.add_argument(
        "--negative-ref",
        default=None,
        metavar="PATH",
        help=(
            "Path to a negative (all-baseline) reference strip image. "
            "Used to calibrate color readings against the user's camera and lighting. "
            "Dramatically improves accuracy when provided."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    image_path = Path(args.image)
    print(f"[Program 2] Analysing strip: {args.image}")
    print(f"            Model:           {args.model}")
    print(f"            Strip config:    {args.config}")
    if args.debug:
        debug_out = args.debug_output or str(image_path.parent / f"{image_path.stem}_debug.png")
        print(f"            Debug image:     {debug_out}")
    if args.negative_ref:
        print(f"            Negative ref:    {args.negative_ref}")

    try:
        model = CalibrationModel.load(args.model)
        analyzer = StripAnalyzer()

        if args.debug:
            raw_results = analyzer.analyze_with_debug(
                args.image,
                model,
                args.config,
                debug_output_path=debug_out,
                manual_pad_h=args.manual_pad_h,
                manual_gap_h=args.manual_gap_h,
                manual_y_offset=args.manual_y_offset,
                negative_image_path=args.negative_ref,
            )
        else:
            raw_results = analyzer.analyze(
                args.image, 
                model, 
                args.config,
                manual_pad_h=args.manual_pad_h,
                manual_gap_h=args.manual_gap_h,
                manual_y_offset=args.manual_y_offset,
                negative_image_path=args.negative_ref,
            )

    except (FileNotFoundError, ValueError, KeyError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    # Convert to AnalysisResult for display / serialisation
    from api.analyzer_api import AnalysisResult
    results = {
        analyte: AnalysisResult(
            analyte=br.analyte,
            color_rgb=br.color_rgb,
            value=br.value,
            unit=br.unit,
            confidence=br.confidence,
        )
        for analyte, br in raw_results.items()
    }

    # Pretty-print results to console
    print("\n" + "=" * 60)
    print("  URINALYSIS STRIP ANALYSIS RESULTS")
    print("=" * 60)
    header = f"{'ANALYTE':<18} {'VALUE':<12} {'UNIT':<14} {'CONFIDENCE'}"
    print(header)
    print("-" * 60)
    for analyte, res in results.items():
        val_str = f"{res.value:.3g}" if isinstance(res.value, float) else str(res.value)
        conf_str = f"{res.confidence * 100:.1f}%"
        print(f"{analyte:<18} {val_str:<12} {res.unit:<14} {conf_str}")
    print("=" * 60)

    json_str = results_to_json(results)

    if args.output:
        with open(args.output, "w") as f:
            f.write(json_str)
        print(f"\n✅  Results saved to: {args.output}")
    else:
        print("\n[JSON Output]")
        print(json_str)


if __name__ == "__main__":
    main()
