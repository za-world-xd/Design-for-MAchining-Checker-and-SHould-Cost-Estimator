# DFM checker and should-cost estimator

Python calculation engine and Streamlit worksheet for early manufacturing estimates in INR.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m streamlit run app.py
```

The Streamlit worksheet supports milling, turning, sheet metal, sand casting and die casting.
Rates in `config/rates.yaml` are illustrative, not vendor quotes. Dimensions use mm,
volume uses cm3, mass uses kg, and all costs use INR.

## Cost basis

Material uses stock volume, density, price per kg and a scrap allowance. Machine cost
uses removed volume divided by an effective removal rate, plus non-cutting and handling
time. Setup and programming are amortised across the batch. Tooling is a fraction of
machine cost. Finishing respects minimum lot charges.

Overhead applies to direct costs; the margin input is a markup on cost plus overhead.
Sheet metal uses the flat blank, thickness-adjusted laser speed, pierces and bend charges.
Casting uses metal yield, weight-based conversion and batch-amortised pattern or die cost.
Process comparisons need an engineering review: a different process may require a different
geometry, material grade, stock shape or secondary operation.

## Manufacturability screening

`config/dfm_thresholds.yaml` controls wall, radius, pocket, drilling, tolerance,
bend-clearance, draft and finish checks. Defaults are heuristics for review with a
shop, not handbook-certified limits. The reference links explain the risks; they
do not validate every numerical default. A clean screening result is not a DFM approval.

PDF exports include cost, findings, assumptions, geometry and a rate/threshold snapshot.
They use INR text so the currency renders with standard PDF fonts.

## Workflow

Choose a starting example, process and material, edit the part form, then calculate.
Inspect the cost table, DFM findings and batch-size chart. PDF, cost CSV and audit JSON
downloads refer to the last submitted snapshot. Form edits need a new calculation.
Changing example, process or material clears the previous estimate.

STEP parsing and automatic feature recognition are not implemented. The form is the
primary input; use CAD measurements for solid volume and finishing surface area.
