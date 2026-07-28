# DFM checker and should-cost estimator

Python calculation engine and Streamlit worksheet for early manufacturing estimates in INR.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\python -m streamlit run app.py
```

The calculation engine supports milling and turning with rectangular and cylindrical stock.
Rates in `config/rates.yaml` are illustrative, not vendor quotes. Dimensions use mm,
volume uses cm3, mass uses kg, and all costs use INR.

## Cost basis

Material uses stock volume, density, price per kg and a scrap allowance. Machine cost
uses removed volume divided by an effective removal rate, plus non-cutting and handling
time. Setup and programming are amortised across the batch. Tooling is a fraction of
machine cost. Finishing respects minimum lot charges.

Overhead applies to direct costs; the margin input is a markup on cost plus overhead.
