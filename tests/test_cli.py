import json

import pytest

from core.__main__ import main
from core.config import ROOT, Rates
from core.estimator import estimate
from core.models import Part


def test_cli_export_can_reproduce_estimate(capsys, tmp_path):
    pdf = tmp_path / "report.pdf"
    assert main([str(ROOT / "examples/milled_bracket.json"), "--pdf", str(pdf)]) == 0
    data = json.loads(capsys.readouterr().out)
    restored = estimate(
        Part.model_validate(data["estimate"]["part"]), Rates.model_validate(data["rates"])
    )
    assert restored.unit_cost == data["unit_cost"]
    assert data["schema_version"] == 1
    assert pdf.read_bytes().startswith(b"%PDF")


def test_cli_invalid_json_has_readable_error(tmp_path, capsys):
    invalid = tmp_path / "bad.json"
    invalid.write_text('{"quantity": 0}')
    with pytest.raises(SystemExit) as error:
        main([str(invalid)])
    assert error.value.code == 2
    assert "Could not estimate part" in capsys.readouterr().err
