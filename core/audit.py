from datetime import datetime
from zoneinfo import ZoneInfo

from core.config import Rates
from core.dfm_rules import Thresholds
from core.models import Estimate, Finding


def audit_payload(
    result: Estimate, findings: list[Finding], rates: Rates, thresholds: Thresholds
) -> dict:
    return {
        "schema_version": 1,
        "generated_at": datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds"),
        "estimate": result.model_dump(mode="json"),
        "unit_cost": result.unit_cost,
        "batch_cost": result.batch_cost,
        "findings": [finding.model_dump() for finding in findings],
        "rates": rates.model_dump(mode="json", by_alias=True),
        "thresholds": thresholds.model_dump(mode="json"),
    }
