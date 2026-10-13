"""Nominal, dimension-driven part families. Dimensions are mm unless labelled otherwise."""

from dataclasses import dataclass
from math import isfinite, pi, sin

from core.models import Hole, Part, PresetSource, Process


@dataclass(frozen=True)
class Parameter:
    key: str
    label: str
    default: float
    minimum: float = 0.01
    maximum: float = 10000
    integer: bool = False
    unit: str = "mm"
    advanced: bool = False


@dataclass(frozen=True)
class Preset:
    label: str
    family: str
    process: Process
    material: str
    description: str
    parameters: tuple[Parameter, ...]
    assumptions: tuple[str, ...]


def dim(key, label, default, minimum=0.01):
    return Parameter(key, label, default, minimum)


SHEET_BEND = (
    "Leg dimensions are outside dimensions at 90 degrees; neutral-axis K-factor is editable.",
    "Flat length uses bend deduction: 2(R + T) - pi/2 * (R + K*T) per bend.",
    "Review the K-factor with the actual material and press tooling. Bend reliefs are excluded.",
    "Material and finishing use developed-blank volume and area.",
)
CASTING = (
    "Nominal open-top box with uniform wall and floor thickness; no lid, ribs or bosses.",
    "Volume ignores draft and corner fillets. Draft remains a separate DFM input.",
    "Core design, shrinkage allowance and post-machining need a foundry process plan.",
)
K_FACTOR = Parameter("k_factor", "Bend K-factor", 0.4, 0.1, 0.5, unit="", advanced=True)
PRESETS = {
    "bush": Preset(
        "Spacer / bush",
        "Turned parts",
        Process.TURNING,
        "aluminium_6061",
        "A cylindrical sleeve with one straight through bore.",
        (
            dim("outer_d", "Outside diameter", 30),
            dim("inner_d", "Bore diameter", 16, 0),
            dim("length", "Length", 25),
        ),
        ("Straight bore; threads, grooves, chamfers and interference fits are excluded.",),
    ),
    "shaft": Preset(
        "Plain shaft",
        "Turned parts",
        Process.TURNING,
        "mild_steel",
        "A solid cylindrical shaft cut and turned from round stock.",
        (dim("diameter", "Shaft diameter", 25), dim("length", "Shaft length", 100)),
        ("No keyways, threads, cross-drilling, grinding or heat treatment by default.",),
    ),
    "stepped_shaft": Preset(
        "Stepped shaft",
        "Turned parts",
        Process.TURNING,
        "mild_steel",
        "Two coaxial diameters with a single shoulder.",
        (
            dim("main_d", "Main diameter", 30),
            dim("journal_d", "Journal diameter", 20),
            dim("main_length", "Main section length", 60),
            dim("journal_length", "Journal length", 30),
        ),
        ("Nominal sharp shoulder; no fillets, grooves, keyways or threads.",),
    ),
    "ring": Preset(
        "Machined washer / ring",
        "Turned parts",
        Process.TURNING,
        "mild_steel",
        "A custom turned ring with a through bore.",
        (
            dim("outer_d", "Outside diameter", 40),
            dim("inner_d", "Inside diameter", 20),
            dim("length", "Thickness", 5),
        ),
        ("Custom machined ring pricing; standard stamped washer retail prices differ.",),
    ),
    "flange": Preset(
        "Drilled circular flange",
        "Milled parts",
        Process.MILLING,
        "aluminium_6061",
        "A circular plate with a central bore and equally spaced bolt holes.",
        (
            dim("outer_d", "Flange diameter", 100),
            dim("inner_d", "Centre bore", 30, 0),
            dim("thickness", "Thickness", 10),
            dim("bolt_d", "Bolt-hole diameter", 8),
            dim("pcd", "Bolt pitch-circle diameter", 70),
            Parameter("bolt_count", "Bolt-hole count", 4, 2, 24, True, ""),
        ),
        (
            "Milled from a square blank; a turned blank plus drilling may cost differently.",
            "Through holes on one bolt circle; no hub, counterbores or threads.",
        ),
    ),
    "mounting_plate": Preset(
        "Four-hole mounting plate",
        "Milled parts",
        Process.MILLING,
        "aluminium_6061",
        "A rectangular plate with four corner mounting holes.",
        (
            dim("length", "Plate length", 100),
            dim("width", "Plate width", 60),
            dim("thickness", "Thickness", 10),
            dim("hole_d", "Hole diameter", 6),
            dim("edge", "Hole-centre edge offset", 12),
        ),
        ("One through hole at each corner, with equal centre-to-edge offsets.",),
    ),
    "block": Preset(
        "Rectangular block",
        "Milled parts",
        Process.MILLING,
        "aluminium_6061",
        "A solid rectangular block with machined faces.",
        (
            dim("length", "Block length", 80),
            dim("width", "Block width", 50),
            dim("height", "Block height", 20),
        ),
        ("No holes or pockets. Stock allowance represents face-machining material.",),
    ),
    "pocket_block": Preset(
        "Pocketed block",
        "Milled parts",
        Process.MILLING,
        "aluminium_6061",
        "A rectangular block with one blind, rounded rectangular pocket.",
        (
            dim("length", "Block length", 100),
            dim("width", "Block width", 60),
            dim("height", "Block height", 25),
            dim("pocket_l", "Pocket length", 60),
            dim("pocket_w", "Pocket width", 30),
            dim("depth", "Pocket depth", 15),
            dim("radius", "Pocket corner radius", 3, 0),
        ),
        ("One flat-bottom pocket; no floor fillets, holes or undercuts.",),
    ),
    "sheet_panel": Preset(
        "Laser-cut rectangular panel",
        "Sheet metal",
        Process.SHEET,
        "mild_steel",
        "A flat rectangular sheet blank with no bends or holes.",
        (
            dim("length", "Panel length", 200),
            dim("width", "Panel width", 120),
            dim("thickness", "Sheet thickness", 2),
        ),
        ("Outer rectangle cut only; one laser pierce and no bends.",),
    ),
    "l_bracket": Preset(
        "Bent L-bracket",
        "Sheet metal",
        Process.SHEET,
        "mild_steel",
        "One 90-degree bend, specified by the two outside leg lengths.",
        (
            dim("leg_a", "Outside leg A", 60),
            dim("leg_b", "Outside leg B", 40),
            dim("width", "Bracket width", 30),
            dim("thickness", "Sheet thickness", 2),
            dim("radius", "Inside bend radius", 2, 0),
            K_FACTOR,
        ),
        SHEET_BEND,
    ),
    "u_channel": Preset(
        "Bent U-channel",
        "Sheet metal",
        Process.SHEET,
        "mild_steel",
        "A channel with two equal 90-degree bends and an open top.",
        (
            dim("base", "Outside base width", 60),
            dim("leg", "Outside leg height", 30),
            dim("length", "Channel length", 100),
            dim("thickness", "Sheet thickness", 2),
            dim("radius", "Inside bend radius", 2, 0),
            K_FACTOR,
        ),
        SHEET_BEND,
    ),
    "cast_housing": Preset(
        "Sand-cast open housing",
        "Cast parts",
        Process.SAND,
        "aluminium_a356",
        "A uniform-wall open box for early casting estimates.",
        (
            dim("length", "Outside length", 120),
            dim("width", "Outside width", 80),
            dim("height", "Outside height", 40),
            dim("wall", "Wall and floor", 4),
        ),
        CASTING,
    ),
    "die_tray": Preset(
        "Die-cast open tray",
        "Cast parts",
        Process.DIE,
        "aluminium_adc12",
        "An open tray with uniform walls and a flat floor.",
        (
            dim("length", "Outside length", 100),
            dim("width", "Outside width", 70),
            dim("height", "Outside height", 25),
            dim("wall", "Wall and floor", 2),
        ),
        CASTING,
    ),
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def build_preset(key: str, parameters: dict | None = None, **settings) -> Part:
    """Derive nominal solid volume, exposed area and DFM features from basic dimensions."""
    if key not in PRESETS:
        raise ValueError("Choose a known part preset")
    preset = PRESETS[key]
    values = {parameter.key: parameter.default for parameter in preset.parameters}
    _require(set(parameters or {}).issubset(values), "Unknown preset dimension")
    values.update(parameters or {})
    for parameter in preset.parameters:
        value = values[parameter.key]
        _require(
            not isinstance(value, bool) and isinstance(value, (int, float)) and isfinite(value),
            f"{parameter.label} must be a finite number",
        )
        _require(
            parameter.minimum <= value <= parameter.maximum,
            f"{parameter.label} must be between {parameter.minimum:g} and {parameter.maximum:g}",
        )
        if parameter.integer:
            _require(int(value) == value, f"{parameter.label} must be a whole number")
    p = values
    holes = []
    derived = {"bends": 0}
    if key in ("bush", "ring", "shaft"):
        d = p.get("outer_d", p.get("diameter"))
        bore, length = p.get("inner_d", 0), p["length"]
        _require(bore < d, "Bore diameter must be smaller than the outside diameter")
        volume = pi / 4 * (d * d - bore * bore) * length
        area = pi * (d + bore) * length + pi / 2 * (d * d - bore * bore)
        width = height = d
        wall = (d - bore) / 2
        if bore:
            holes = [Hole(diameter_mm=bore, depth_mm=length)]
    elif key == "stepped_shaft":
        d, journal = p["main_d"], p["journal_d"]
        _require(journal <= d, "Journal diameter must not exceed the main diameter")
        length = p["main_length"] + p["journal_length"]
        width = height = d
        wall = journal / 2
        volume = pi / 4 * (d * d * p["main_length"] + journal * journal * p["journal_length"])
        area = pi * (d * p["main_length"] + journal * p["journal_length"]) + pi / 2 * d * d
    elif key == "flange":
        d, bore, t, bolt, pcd = (p[k] for k in ("outer_d", "inner_d", "thickness", "bolt_d", "pcd"))
        count = int(p["bolt_count"])
        spacing = pcd * sin(pi / count)
        _require(
            bore < d and pcd + bolt < d and pcd - bolt > bore,
            "Bolt holes must fit between the centre bore and flange edge",
        )
        _require(spacing > bolt, "Adjacent bolt holes overlap; enlarge the bolt circle")
        length = width = d
        height = t
        wall = min(t, (d - pcd - bolt) / 2, (pcd - bolt - bore) / 2, spacing - bolt)
        volume = pi / 4 * (d * d - bore * bore - count * bolt * bolt) * t
        area = pi * (d + bore) * t + pi / 2 * (d * d - bore * bore)
        area += count * (pi * bolt * t - pi / 2 * bolt * bolt)
        holes = [Hole(diameter_mm=bolt, depth_mm=t, count=count)]
        if bore:
            holes.append(Hole(diameter_mm=bore, depth_mm=t))
    elif key in ("block", "mounting_plate", "pocket_block", "sheet_panel"):
        length, width = p["length"], p["width"]
        height = p.get("height", p.get("thickness"))
        volume = length * width * height
        area = 2 * (length * width + length * height + width * height)
        wall = min(length, width, height)
        if key == "mounting_plate":
            hole, edge = p["hole_d"], p["edge"]
            _require(
                edge > hole / 2 and length - 2 * edge > hole and width - 2 * edge > hole,
                "Corner holes must clear the plate edges and must not overlap",
            )
            volume -= 4 * pi / 4 * hole * hole * height
            area += 4 * (pi * hole * height - pi / 2 * hole * hole)
            wall = min(height, edge - hole / 2)
            holes = [Hole(diameter_mm=hole, depth_mm=height, count=4)]
        elif key == "pocket_block":
            a, b, depth, radius = (p[k] for k in ("pocket_l", "pocket_w", "depth", "radius"))
            _require(
                a < length and b < width and depth < height,
                "Pocket must leave positive side walls and a floor",
            )
            _require(radius <= min(a, b) / 2, "Corner radius exceeds half the pocket width")
            pocket_area = a * b - (4 - pi) * radius * radius
            pocket_perimeter = 2 * (a + b) - 8 * radius + 2 * pi * radius
            volume -= pocket_area * depth
            area += pocket_perimeter * depth
            wall = min((length - a) / 2, (width - b) / 2, height - depth)
            derived |= {
                "pocket_depth_mm": depth,
                "pocket_width_mm": min(a, b),
                "corner_radius_mm": radius,
            }
    elif key in ("l_bracket", "u_channel"):
        t, radius, k = p["thickness"], p["radius"], p["k_factor"]
        deduction = 2 * (radius + t) - pi / 2 * (radius + k * t)
        if key == "l_bracket":
            _require(
                min(p["leg_a"], p["leg_b"]) > radius + t,
                "Both outside legs must extend beyond the bend radius plus thickness",
            )
            length, width = p["leg_a"] + p["leg_b"] - deduction, p["width"]
            bends = 1
        else:
            _require(
                p["base"] > 2 * (radius + t) and p["leg"] > radius + t,
                "Base and legs must leave room for both bends",
            )
            length, width = p["length"], p["base"] + 2 * p["leg"] - 2 * deduction
            bends = 2
        height = wall = t
        volume = length * width * t
        area = 2 * (length * width + t * (length + width))
        derived |= {"bends": bends, "bend_radius_mm": radius}
    else:
        length, width, height, wall = (p[k] for k in ("length", "width", "height", "wall"))
        _require(
            2 * wall < min(length, width) and wall < height,
            "Walls and floor must leave a positive internal cavity",
        )
        volume = length * width * height - (length - 2 * wall) * (width - 2 * wall) * (
            height - wall
        )
        area = 2 * length * width + 2 * height * (length + width)
        area += 2 * (height - wall) * (length + width - 4 * wall)
    if preset.process == Process.SHEET:
        derived |= {"cut_perimeter_mm": 2 * (length + width), "pierces": 1}
    _require(volume > 0 and area > 0, "Dimensions do not describe a positive solid")
    default_ra = {
        Process.MILLING: 3.2,
        Process.TURNING: 1.6,
        Process.SHEET: 6.3,
        Process.SAND: 12.5,
        Process.DIE: 3.2,
    }
    part_data = {
        "name": preset.label,
        "process": preset.process,
        "material": preset.material,
        "length_mm": length,
        "width_mm": width,
        "height_mm": height,
        "volume_cm3": volume / 1000,
        "surface_area_cm2": area / 100,
        "wall_mm": wall,
        "max_wall_mm": wall,
        "holes": holes,
        "finish_ra_um": default_ra[preset.process],
        **derived,
        "preset_source": PresetSource(
            key=key, label=preset.label, parameters=values, assumptions=list(preset.assumptions)
        ),
    }
    allowed = {
        "quantity",
        "material",
        "secondary",
        "overhead_pct",
        "margin_pct",
        "tolerance_it",
        "finish_ra_um",
        "supported",
        "draft_deg",
    }
    _require(
        set(settings).issubset(allowed), "Only costing and finish settings may override a preset"
    )
    return Part.model_validate(part_data | settings)
