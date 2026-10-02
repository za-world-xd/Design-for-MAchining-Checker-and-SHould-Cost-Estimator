from pathlib import Path

import yaml
from pydantic import Field, model_validator

from core.config import ROOT, ConfigModel, Positive, Rates
from core.models import Finding, Part, Process


class Thresholds(ConfigModel):
    metadata: dict
    max_pocket_ratio: Positive
    min_cutter_radius_mm: Positive
    max_hole_ratio: Positive
    max_turning_ratio: Positive
    min_tolerance_it: int = Field(ge=1, le=16)
    min_bend_radius_factor: Positive
    min_hole_edge_factor: Positive
    min_hole_bend_factor: Positive
    max_cast_wall_ratio: Positive
    min_draft_deg: Positive
    minimum_ra: dict[Process, Positive]

    @model_validator(mode="after")
    def require_process_finish_limits(self):
        if set(self.minimum_ra) != set(Process):
            raise ValueError("Every process needs a minimum Ra screening threshold")
        return self


def load_thresholds(path: Path | None = None) -> Thresholds:
    with (path or ROOT / "config" / "dfm_thresholds.yaml").open(encoding="utf-8") as stream:
        try:
            return Thresholds.model_validate(yaml.safe_load(stream))
        except yaml.YAMLError as exc:
            raise ValueError("DFM thresholds contain invalid YAML") from exc


def milling_rules(part: Part, cfg: Thresholds) -> list[Finding]:
    findings = []
    if part.pocket_depth_mm / part.pocket_width_mm > cfg.max_pocket_ratio:
        findings.append(
            Finding(
                rule="mill.deep_pocket",
                severity="warning",
                message="Pocket depth-to-width ratio exceeds the screening limit.",
                suggestion="Widen or shorten the pocket, or review long-tool access with the shop.",
            )
        )
    if part.corner_radius_mm < cfg.min_cutter_radius_mm:
        findings.append(
            Finding(
                rule="mill.corner",
                severity="critical",
                message="Internal radius is below the configured available cutter radius.",
                suggestion=f"Use {cfg.min_cutter_radius_mm:g} mm or review another process.",
            )
        )
    return findings


def turning_rules(part: Part, cfg: Thresholds) -> list[Finding]:
    if part.length_mm / part.width_mm > cfg.max_turning_ratio and not part.supported:
        return [
            Finding(
                rule="turn.slender",
                severity="warning",
                message="Unsupported length-to-diameter ratio exceeds the screening limit.",
                suggestion="Plan a tailstock or steady rest, or shorten the unsupported length.",
            )
        ]
    return []


def sheet_rules(part: Part, cfg: Thresholds) -> list[Finding]:
    findings = []
    checks = [
        (
            part.bends > 0 and part.bend_radius_mm < part.height_mm * cfg.min_bend_radius_factor,
            "sheet.bend_radius",
            "Bend radius is small relative to sheet thickness.",
            "Increase the inside radius or confirm the alloy, grain direction and tooling.",
        ),
        (
            part.hole_edge_mm is not None
            and part.hole_edge_mm < part.height_mm * cfg.min_hole_edge_factor,
            "sheet.hole_edge",
            "Hole edge clearance is below the screening limit.",
            "Increase the distance measured from the hole edge to the blank edge.",
        ),
        (
            part.bends > 0
            and part.hole_bend_mm is not None
            and part.hole_bend_mm < part.height_mm * cfg.min_hole_bend_factor,
            "sheet.hole_bend",
            "Hole-to-bend clearance is below the screening limit.",
            "Move the hole away from the bend tangent or cut it after bending.",
        ),
    ]
    for applies, rule, message, suggestion in checks:
        if applies:
            findings.append(
                Finding(rule=rule, severity="warning", message=message, suggestion=suggestion)
            )
    return findings


def casting_rules(part: Part, cfg: Thresholds) -> list[Finding]:
    findings = []
    if part.max_wall_mm / part.wall_mm > cfg.max_cast_wall_ratio:
        findings.append(
            Finding(
                rule="cast.wall_variation",
                severity="warning",
                message="Wall thickness variation may produce hot spots and uneven solidification.",
                suggestion="Core out thick regions and blend wall transitions.",
            )
        )
    if part.draft_deg < cfg.min_draft_deg:
        findings.append(
            Finding(
                rule="cast.draft",
                severity="critical",
                message="Draft angle is below the configured pattern or die release allowance.",
                suggestion="Agree draft direction and angle with the foundry or die caster.",
            )
        )
    return findings


def check_dfm(part: Part, rates: Rates, cfg: Thresholds) -> list[Finding]:
    findings = []
    minimum_wall = rates.materials[part.material].min_wall_mm
    wall = part.height_mm if part.process == Process.SHEET else part.wall_mm
    if wall < minimum_wall:
        findings.append(
            Finding(
                rule="common.wall",
                severity="warning",
                message=f"Wall {wall:g} mm is below the {minimum_wall:g} mm material heuristic.",
                suggestion="Increase thickness or review clamping and distortion with the shop.",
            )
        )
    if part.tolerance_it < cfg.min_tolerance_it:
        findings.append(
            Finding(
                rule="common.tolerance",
                severity="info",
                message="Tight tolerance may require added inspection or secondary machining.",
                suggestion="Limit tight tolerances to functional features; obtain a process plan.",
            )
        )
    if part.finish_ra_um < cfg.minimum_ra[part.process]:
        findings.append(
            Finding(
                rule="common.finish",
                severity="warning",
                message="Requested Ra is finer than the configured process screening capability.",
                suggestion="Specify local finish requirements and price secondary finishing.",
            )
        )
    if part.process in (Process.MILLING, Process.TURNING):
        for index, hole in enumerate(part.holes, 1):
            if hole.depth_mm / hole.diameter_mm > cfg.max_hole_ratio:
                findings.append(
                    Finding(
                        rule=f"common.deep_hole.{index}",
                        severity="warning",
                        message=f"Hole group {index} exceeds the drilling depth-to-diameter limit.",
                        suggestion="Reduce depth, enlarge the hole or plan specialist drilling.",
                    )
                )
    if part.process == Process.MILLING:
        findings += milling_rules(part, cfg)
    elif part.process == Process.TURNING:
        findings += turning_rules(part, cfg)
    elif part.process == Process.SHEET:
        findings += sheet_rules(part, cfg)
    else:
        findings += casting_rules(part, cfg)
    order = {"critical": 0, "warning": 1, "info": 2}
    return sorted(findings, key=lambda finding: order[finding.severity])
