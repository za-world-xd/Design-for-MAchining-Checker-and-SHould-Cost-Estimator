from streamlit.testing.v1 import AppTest

from core.config import ROOT


def custom_app(timeout=30):
    app = AppTest.from_file(ROOT / "app.py", default_timeout=timeout)
    app.session_state["entry_mode"] = "Custom / STEP"
    return app.run()
