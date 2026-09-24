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
An alternative material/process table compares the same submitted envelope and volume.
Unsupported material, geometry and finishing combinations show a validation message.

STEP parsing and automatic feature recognition are not implemented. The form is the
primary input; use CAD measurements for solid volume and finishing surface area.

## Check the calculations

```powershell
.venv\Scripts\python -m pytest -q
.venv\Scripts\ruff check .
```

Three illustrative parts in `examples/` have independent component calculations in
`examples/hand_calculations.csv`. Tests compare every component with these values.
The milling example uses 138 cm3 stock, 78 cm3 removal and a 5.68 minute cycle.
The turning example uses cylindrical stock of 36.1283155 cm3. The sheet example
uses a 12 cm3 blank, 75% nesting utilisation, 320 mm cut and two bends.
Vendor quote validation is pending. No accuracy claim is made against real quotes.

## Command line

```powershell
.venv\Scripts\python -m core examples/milled_bracket.json --pdf output/bracket.pdf
```

The command prints a JSON audit with the submitted geometry, costs, rates and thresholds.
Use `--rates path/to/rates.yaml` and `--thresholds path/to/thresholds.yaml` for alternate
cards. JSON input supports multiple hole groups, each with diameter, depth and count.
The worksheet currently accepts one group of identical holes.
