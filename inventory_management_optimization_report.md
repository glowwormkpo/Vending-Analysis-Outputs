# Inventory Management Optimization Report

## Executive Summary

This project analyzed industrial vending-machine inventory turnover and restocking data to forecast demand and recommend restocking levels. The inventory dataset contains 38,982 records across 82 SKUs and 5 devices, covering 2022-02-23 to 2024-02-23. The restock dataset contains 722 records from 2023-03-24 to 2024-03-18.

The analysis found 317,528 total units dispensed. Demand is concentrated among a small set of SKUs, and device usage is moderately balanced across five vending machines. A 7-day rolling-average forecast provides a transparent baseline, with RMSE of 280.29 units on the final 30-day test period.

## Data Cleaning and Preparation

Both datasets were checked for missing values and duplicates. No missing values were found. Date columns were parsed into datetime fields, and quantity/cost columns were converted to numeric values. The inventory file includes `qty_dispensed`, while the restock file includes restock order records and `total` spend rather than restocked unit quantity.

## Exploratory and Statistical Analysis

The analysis generated descriptive statistics for numeric and categorical fields, then aggregated demand by date, SKU, month, weekday, and device. Time features such as month, week number, day of week, weekend flag, lag values, and rolling averages were created to support seasonality analysis and forecasting.

## Product Insights

The highest-turnover SKU was `b1cfc8c80d03027941b0bce8d2ff3deb`, with 21,845 units dispensed. The top five SKUs were:

| SKU | Total Dispensed | Coefficient of Variation |
|---|---:|---:|
| `b1cfc8c80d03027941b0bce8d2ff3deb` | 21,845 | 0.450 |
| `be61be55295db1941eaf232ee6288fa7` | 17,273 | 0.575 |
| `93d664dddeea2dd49decf97035051e92` | 16,395 | 0.490 |
| `9a154810b166b91ae0c3d0cd84fb7e05` | 16,083 | 0.364 |
| `da3562c59621dd135d3f0255d3fb66aa` | 14,683 | 0.452 |

High-turnover products should receive priority in reorder planning. SKUs with high coefficient of variation should receive additional safety-stock attention because their demand is less predictable.

## Device Utilization

The highest-utilization device was `device_6726f2a054f54836aaabe8c7643286bc`, representing 22.17% of total dispensed quantity. The two highest-use devices together represent 43.50% of demand.

| Device | Total Dispensed | Utilization Share |
|---|---:|---:|
| `device_6726f2a054f54836aaabe8c7643286bc` | 70,397 | 22.17% |
| `device_65ae7ea424c57d46ac409256fe359349` | 67,741 | 21.33% |
| `device_c287be7e02167387bf9e7eca061ce5b5` | 61,034 | 19.22% |
| `device_af645ebf4c96eb6e430529a2a9913686` | 59,568 | 18.76% |
| `device_0749c361d8ac7047c2f98fbcb2eadd16` | 58,788 | 18.51% |

## Forecasting Results

The baseline model used a 7-day rolling average and evaluated performance on the final 30 days.

| Model | MAE | RMSE | MAPE |
|---|---:|---:|---:|
| 7-day rolling average | 145.20 | 280.29 | 60.54% |

The high MAPE indicates meaningful demand volatility. The baseline is useful for comparison, but SKU/device-level models are recommended for production use.

## Correlation Findings

Same-day correlations between demand and restock activity were weakly negative:

| Relationship | Correlation |
|---|---:|
| quantity_dispensed vs restock_events | -0.280 |
| quantity_dispensed vs restock_total_cost | -0.249 |

This should not be interpreted as restocking reducing demand. It likely reflects operational timing, where restocking happens after demand has already occurred or on a separate schedule. Lagged correlation analysis should be added in a future iteration.

## Restocking Recommendations

Recommendations were calculated for the top 20 SKUs using forecasted daily demand, SKU demand share, a 7-day lead time, and a 20% service buffer. The top recommendation is:

- SKU: `b1cfc8c80d03027941b0bce8d2ff3deb`
- Expected daily demand: 22.83 units
- Recommended reorder point: 192 units
- Recommended weekly restock quantity: 192 units

## Recommendations

1. Prioritize high-turnover SKUs in replenishment planning.
2. Add current on-hand inventory so reorder points can be converted into exact order quantities.
3. Apply higher safety stock to high-variance SKUs.
4. Monitor the two highest-utilization devices more closely because they account for a large share of total demand.
5. Build SKU/device-level forecasting models after this baseline, especially for the highest-turnover items.
6. Study lagged restock effects to better understand how restocking timing relates to future dispensing activity.

## Conclusion

The project demonstrates a complete analytics workflow from cleaning and exploration to forecasting and inventory recommendations. The results show that simple aggregate forecasting is informative but not sufficient for highly variable vending-machine demand. A production inventory process should combine SKU-level forecasts, device-level utilization, current inventory, lead times, and service-level targets.
