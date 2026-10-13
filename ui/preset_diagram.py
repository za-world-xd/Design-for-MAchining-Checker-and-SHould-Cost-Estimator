from html import escape

from core.presets import PRESETS


def preset_diagram(key, p):
    """A schematic plan/section view tied to the current dimensions, not a CAD drawing."""
    title = PRESETS[key].label
    drawing = ""
    if key in ("bush", "ring", "shaft", "flange"):
        diameter = p.get("outer_d", p.get("diameter"))
        scale = 110 / diameter
        drawing = '<circle cx="120" cy="78" r="55"/>'
        bore = p.get("inner_d", 0)
        if bore:
            drawing += f'<circle cx="120" cy="78" r="{bore * scale / 2}" fill="white"/>'
        if key == "flange":
            from math import cos, pi, sin

            for i in range(int(p["bolt_count"])):
                angle = 2 * pi * i / p["bolt_count"]
                x = 120 + p["pcd"] * scale / 2 * cos(angle)
                y = 78 + p["pcd"] * scale / 2 * sin(angle)
                drawing += f'<circle cx="{x}" cy="{y}" r="{p["bolt_d"] * scale / 2}" fill="white"/>'
        caption = (
            f"OD {diameter:g} mm; length / thickness {p.get('length', p.get('thickness')):g} mm"
        )
    elif key == "stepped_shaft":
        scale = min(190 / (p["main_length"] + p["journal_length"]), 100 / p["main_d"])
        a, b, d, journal = [
            p[k] * scale for k in ("main_length", "journal_length", "main_d", "journal_d")
        ]
        shoulder = (d - journal) / 2
        drawing = (
            f'<path d="M25,{78 - d / 2} h{a} v{shoulder} h{b} v{journal} '
            f'h{-b} v{shoulder} h{-a} Z"/>'
        )
        caption = f"Main OD {p['main_d']:g}; journal OD {p['journal_d']:g} mm"
    elif key in ("l_bracket", "u_channel"):
        width = p.get("leg_a", p.get("base"))
        height = p.get("leg_b", p.get("leg"))
        scale = min(185 / width, 105 / height)
        w, h, t = width * scale, height * scale, p["thickness"] * scale
        if key == "l_bracket":
            points = [(0, 0), (t, 0), (t, h - t), (w, h - t), (w, h), (0, h)]
        else:
            points = [
                (0, 0),
                (t, 0),
                (t, h - t),
                (w - t, h - t),
                (w - t, 0),
                (w, 0),
                (w, h),
                (0, h),
            ]
        drawing = '<polygon points="' + " ".join(f"{25 + x},{20 + y}" for x, y in points) + '"/>'
        caption = f"Outside section {width:g} x {height:g}; T {p['thickness']:g} mm"
    else:
        width, height = p["length"], p["width"]
        scale = min(185 / width, 105 / height)
        w, h = width * scale, height * scale
        drawing = f'<rect x="25" y="20" width="{w}" height="{h}"/>'
        if key == "mounting_plate":
            for x in (p["edge"], width - p["edge"]):
                for y in (p["edge"], height - p["edge"]):
                    drawing += (
                        f'<circle cx="{25 + x * scale}" cy="{20 + y * scale}" '
                        f'r="{p["hole_d"] * scale / 2}" fill="white"/>'
                    )
        if key in ("pocket_block", "cast_housing", "die_tray"):
            inset_x = (width - p["pocket_l"]) / 2 if key == "pocket_block" else p["wall"]
            inset_y = (height - p["pocket_w"]) / 2 if key == "pocket_block" else p["wall"]
            r = p.get("radius", 0) * scale
            inner_w, inner_h = w - 2 * inset_x * scale, h - 2 * inset_y * scale
            drawing += (
                f'<rect x="{25 + inset_x * scale}" y="{20 + inset_y * scale}" '
                f'width="{inner_w}" height="{inner_h}" rx="{r}" fill="white"/>'
            )
        caption = f"Plan {width:g} x {height:g} mm"
    description = "; ".join(
        f"{parameter.label}: {p[parameter.key]:g} {parameter.unit}"
        for parameter in PRESETS[key].parameters
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 180"
        width="100%" height="230" role="img" aria-label="{escape(title)} schematic">
      <title>{escape(title)}</title><desc>{escape(description)}</desc>
      <g fill="#eef1ee" stroke="#35463b" stroke-width="1.7">{drawing}</g>
      <text x="120" y="158" text-anchor="middle" font-family="sans-serif"
        font-size="10" fill="#35463b">{escape(caption)}</text></svg>'''
