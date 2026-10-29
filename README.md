# Industrial Vending Demand Forecasting

> Data Engineer Academy module project: demand forecasting and restocking for industrial vending machines.

This folder contains a dependency-light Python pipeline for the vending-machine
forecasting assignment.

## Inputs

Expected CSV files:

- `Inventory_Turnover.csv`
- `Restock_data.csv`

The script can auto-detect likely date, SKU, device, quantity, and cost columns
from common column names. If the files use unusual headers, update the detection
rules near the top of `vending_demand_forecasting.py`.

## Run

From this folder:

```bash
/Users/jerrywyatt/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 vending_demand_forecasting.py \
  --inventory Inventory_Turnover.csv \
  --restock Restock_data.csv \
  --outdir forecast_outputs
```

Or pass absolute paths to the two CSV files.

## Outputs

The script generates:

- `vending_demand_forecasting_report.html`: self-contained report with summary tables and SVG charts.
- `daily_dispense_restock.csv`: daily demand/restock trend data.
- `top_sku_turnover_and_variability.csv`: SKU turnover and demand variability.
- `sku_monthly_seasonality.csv`: monthly SKU demand shares.
- `device_utilization.csv`: vending-machine utilization ranking.
- `dispense_restock_correlations.csv`: demand/restock correlation checks.
- `forecast_and_backtest.csv`: holdout predictions plus future demand forecast.
- `forecast_metrics.csv`: MAE, RMSE, and MAPE for the baseline model.
- `restocking_recommendations.csv`: reorder-point and weekly-restock suggestions.

## Method Summary

The analysis follows the referenced time-series guidance:

- Clean dates, missing values, duplicates, and numeric fields.
- Aggregate dispensing and restocking by day.
- Add calendar features such as month, weekday, week number, and weekend flag.
- Inspect demand trends, seasonality, SKU variability, and device utilization.
- Evaluate a transparent 7-day rolling-average baseline forecast with a holdout split.
- Convert expected demand into reorder points using lead time and service buffer.

The rolling-average model is a practical benchmark. If the available history is
long and regular enough, it can be extended with ARIMA/SARIMA, exponential
smoothing, or supervised lag-feature models.
