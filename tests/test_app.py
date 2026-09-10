from streamlit.testing.v1 import AppTest

from core.config import ROOT


def number(app, label):
    return next(item for item in app.number_input if item.label == label)


def select(app, label):
    return next(item for item in app.selectbox if item.label == label)


def test_form_empty_calculate_error_and_result_reset():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    assert not app.exception
    assert "Enter a part above" in app.info[0].value
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "₹311.20"
    assert len(app.get("download_button")) == 3
    number(app, "Finished volume (cm³; 0 uses envelope)").set_value(99999)
    app.button[0].click().run()
    assert not app.exception
    assert app.error
    assert len(app.metric) == 0
    select(app, "Starting example").select("Turned spacer").run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
    select(app, "Manufacturing process").select("Sheet metal").run()
    assert len(app.metric) == 0


def test_sheet_and_casting_and_alternative_processes():
    app = AppTest.from_file(ROOT / "app.py", default_timeout=30).run()
    select(app, "Starting example").select("Sheet bracket").run()
    app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "₹75.96"
    select(app, "Alternative process").select("Die casting").run()
    assert not app.exception
    select(app, "Manufacturing process").select("Sand casting").run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
    select(app, "Manufacturing process").select("Die casting").run()
    app.button[0].click().run()
    assert not app.exception
    assert len(app.metric) == 3
