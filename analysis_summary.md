# Industrial Vending Demand Forecasting Summary

## Dataset Overview

- Inventory turnover records: 38,982
- Restock records: 722
- Dispense date range: 2022-02-23 to 2024-02-23
- Restock date range: 2023-03-24 to 2024-03-18
- Unique SKUs: 82
- Unique vending devices: 5
- Total quantity dispensed: 317,528
- Total restock spend: 196,753.13 USD

No missing values were found in either input file.

## Method

The analysis follows a standard time-series workflow:

1. Cleaned duplicate rows, parsed date fields, and converted numeric fields.
2. Aggregated dispensing and restocking activity by day.
3. Created calendar features including month, day of week, week number, and weekend flag.
4. Measured SKU turnover, SKU demand variability, monthly SKU seasonality, and device utilization.
5. Compared daily demand with restock event frequency and restock cost.
6. Built a transparent 7-day rolling-average baseline forecast and evaluated it on the final 30 days.
7. Converted expected demand into reorder-point and weekly-restock recommendations using a 7-day lead time and 20% service buffer.

## Forecast Performance

- Model: 7-day rolling average
- Holdout period: 30 days
- MAE: 145.20 units
- RMSE: 280.29 units
- MAPE: 60.54%

The model is intentionally simple and useful as a baseline. The high percentage error suggests that demand is volatile enough that a stronger model should be considered if higher accuracy is required.

## Highest-Turnover SKUs

The top SKU by total dispensed quantity was `b1cfc8c80d03027941b0bce8d2ff3deb` with 21,845 units. The next highest SKUs were:

- `be61be55295db1941eaf232ee6288fa7`: 17,273 units
- `93d664dddeea2dd49decf97035051e92`: 16,395 units
- `9a154810b166b91ae0c3d0cd84fb7e05`: 16,083 units
- `da3562c59621dd135d3f0255d3fb66aa`: 14,683 units

These items should receive priority in inventory planning because they drive the largest share of demand.

## Device Utilization

Demand was spread across five devices, but utilization was not perfectly even:

- `device_6726f2a054f54836aaabe8c7643286bc`: 70,397 units, 22.17% share
- `device_65ae7ea424c57d46ac409256fe359349`: 67,741 units, 21.33% share
- `device_c287be7e02167387bf9e7eca061ce5b5`: 61,034 units, 19.22% share
- `device_af645ebf4c96eb6e430529a2a9913686`: 59,568 units, 18.76% share
- `device_0749c361d8ac7047c2f98fbcb2eadd16`: 58,788 units, 18.51% share

The first two machines account for about 43.5% of total demand and may require closer restocking attention.

## Restocking Relationships

Daily dispensed quantity had weak negative correlation with restock activity:

- Demand vs restock events: -0.280
- Demand vs restock cost: -0.249

This does not mean restocking reduces demand. It more likely reflects timing differences: restocks may happen after inventory depletion or on operational schedules that do not align with same-day demand. Lagged correlation would be a useful next step.

## Restocking Recommendation Example

Using the baseline forecast, 7-day lead time, and 20% buffer, the top SKU recommendation is:

- SKU `b1cfc8c80d03027941b0bce8d2ff3deb`
- Expected daily demand: 22.83 units
- Recommended reorder point: 192 units
- Recommended weekly restock quantity: 192 units

Full recommendations for the top 20 SKUs are available in `restocking_recommendations.csv`.

## Suggested Next Steps

- Add current on-hand inventory by SKU/device so reorder recommendations can become actionable order quantities.
- Evaluate lagged relationships between restocking and demand.
- Try stronger forecasting models such as SARIMA, exponential smoothing, or supervised lag-feature models.
- Forecast separately by SKU and device for high-turnover products instead of only forecasting aggregate demand.
