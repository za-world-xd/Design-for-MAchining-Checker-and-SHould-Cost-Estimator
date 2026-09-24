import argparse
import json
from pathlib import Path

from core.audit import audit_payload
from core.config import load_rates
from core.dfm_rules import check_dfm, load_thresholds
from core.estimator import estimate
from core.models import Part
from core.report import build_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Estimate a JSON part in INR and screen DFM risks")
    parser.add_argument(
        "part", type=Path, help="Part JSON, for example examples/milled_bracket.json"
    )
    parser.add_argument("--rates", type=Path, help="Override the YAML rate card")
    parser.add_argument("--thresholds", type=Path, help="Override YAML screening thresholds")
    parser.add_argument("--pdf", type=Path, help="Write a PDF report to this path")
    args = parser.parse_args(argv)
    try:
        part = Part.model_validate_json(args.part.read_text(encoding="utf-8"))
        rates = load_rates(args.rates)
        thresholds = load_thresholds(args.thresholds)
        result = estimate(part, rates)
        findings = check_dfm(part, rates, thresholds)
        if args.pdf:
            args.pdf.parent.mkdir(parents=True, exist_ok=True)
            args.pdf.write_bytes(build_report(result, findings, rates, thresholds))
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Could not estimate part: {exc}\n")
    print(json.dumps(audit_payload(result, findings, rates, thresholds), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
