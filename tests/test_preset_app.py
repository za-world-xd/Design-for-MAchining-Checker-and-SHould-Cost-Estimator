from pathlib import Path
from xml.etree import ElementTree

import fitz
import pytest
from streamlit.testing.v1 import AppTest

from core.presets import PRESETS
from tests.test_app import number, select
from ui.preset_diagram import preset_diagram

ROOT = Path(__file__).resolve().parents[1]


def preset_app(key=None):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    if key:
        select(app, "Common part").select(key).run()
    return app


def test_empty_catalogue_has_no_estimate():
    app = preset_app()
    assert not app.exception
    assert "Choose a part type" in app.info[-1].value
    assert not app.metric
    assert not app.get("download_button")


@pytest.mark.parametrize("key", PRESETS)
def test_each_preset_can_be_estimated_and_exported(key):
    app = preset_app(key)
    assert not app.exception
    assert not app.error
    assert len(app.metric) == 3
    assert len(app.get("download_button")) == 3
    result, _, pdf, _, _, audit = app.session_state["result"]
    assert result.part.preset_source.key == key
    assert audit["estimate"]["part"]["preset_source"]["key"] == key
    with fitz.open(stream=pdf, filetype="pdf") as report:
        text = "".join(page.get_text() for page in report)
    assert PRESETS[key].label in text
    assert "preset_source.parameters" in text


def test_dimension_edits_refresh_cost_and_invalid_geometry_clears_exports():
    app = preset_app("bush")
    before = app.session_state["result"][0]
    number(app, "Outside diameter (mm)").set_value(40).run()
    after = app.session_state["result"][0]
    assert after.mass_kg > before.mass_kg
    assert after.unit_cost != before.unit_cost
    assert after.part.preset_source.parameters["outer_d"] == 40
    number(app, "Bore diameter (mm)").set_value(45).run()
    assert not app.exception
    assert app.error
    assert not app.metric
    assert not app.get("download_button")
    assert "result" not in app.session_state
    number(app, "Bore diameter (mm)").set_value(20).run()
    assert len(app.metric) == 3
    number(app, "Batch quantity").set_value(500).run()
    assert app.session_state["result"][0].part.quantity == 500


def test_family_filter_clears_previous_estimate():
    app = preset_app("bush")
    select(app, "Part family").select("Sheet metal").run()
    assert not app.exception
    assert not app.metric
    assert "Spacer / bush" not in select(app, "Common part").options


def test_custom_mode_does_not_reuse_preset_geometry():
    app = preset_app("bush")
    app.radio(key="entry_mode").set_value("Custom / STEP").run()
    assert not app.metric
    app.button[0].click().run()
    assert not app.exception
    assert app.session_state["result"][0].part.preset_source is None
    app.radio(key="entry_mode").set_value("Common part presets").run()
    assert not app.metric


def test_bend_assumption_changes_developed_blank_and_audit():
    app = preset_app("l_bracket")
    before = app.session_state["result"][0].part
    number(app, "Bend K-factor").set_value(0.5).run()
    after = app.session_state["result"][0].part
    assert after.net_volume_cm3 > before.net_volume_cm3
    assert after.preset_source.parameters["k_factor"] == 0.5


@pytest.mark.parametrize("key,preset", PRESETS.items())
def test_diagrams_are_accessible_valid_svg(key, preset):
    svg = ElementTree.fromstring(preset_diagram(key, {p.key: p.default for p in preset.parameters}))
    assert svg.attrib["role"] == "img"
    assert preset.label in svg.attrib["aria-label"]
    assert svg.find("{http://www.w3.org/2000/svg}title") is not None
