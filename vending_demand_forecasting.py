#!/usr/bin/env python3
"""
Industrial vending demand forecasting analysis.

Place Inventory_Turnover.csv and Restock_data.csv in the same folder as this
script, or pass their paths with --inventory and --restock. The script creates
cleaned data, EDA summaries, SKU/device analysis, forecast outputs, and a
self-contained HTML report.
"""

from __future__ import annotations

import argparse
import html
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DATE_HINTS = ("date", "time", "dispense", "restock", "transaction")
SKU_HINTS = ("sku", "item", "part", "product")
DEVICE_HINTS = ("device", "machine", "vending", "coil", "location")
QTY_HINTS = ("qty", "quantity", "dispensed", "usage", "used", "turnover", "issued")
RESTOCK_QTY_HINTS = ("restock", "replenish", "refill", "quantity", "qty")
COST_HINTS = ("cost", "price", "value", "amount", "total")


@dataclass
class ColumnMap:
    date: str | None
    sku: str | None
    device: str | None
    quantity: str | None
    cost: str | None


def normalize_name(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in str(name)).strip("_")


def score_column(column: str, hints: Iterable[str]) -> int:
    col = normalize_name(column)
    return sum(1 for hint in hints if hint in col)


def pick_column(df: pd.DataFrame, hints: Iterable[str], numeric: bool = False) -> str | None:
    candidates: list[tuple[int, str]] = []
    for col in df.columns:
        if numeric and not pd.api.types.is_numeric_dtype(pd.to_numeric(df[col], errors="coerce")):
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().mean() < 0.5:
                continue
        if numeric:
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().mean() < 0.5:
                continue
        score = score_column(col, hints)
        if score:
            candidates.append((score, col))
    if candidates:
        return sorted(candidates, key=lambda x: (-x[0], str(x[1]).lower()))[0][1]
    return None


def pick_date_column(df: pd.DataFrame) -> str | None:
    hinted = pick_column(df, DATE_HINTS)
    if hinted:
        return hinted
    best_col = None
    best_rate = 0.0
    for col in df.columns:
        parsed = pd.to_datetime(df[col], errors="coerce")
        rate = parsed.notna().mean()
        if rate > best_rate and rate >= 0.5:
            best_col = col
            best_rate = rate
    return best_col


def parse_datetime_series(series: pd.Series) -> pd.Series:
    sample = series.dropna().astype(str).head(25)
    dayfirst_votes = sample.str.match(r"^\d{1,2}[-/]\d{1,2}[-/]\d{4}").sum()
    if dayfirst_votes >= max(1, len(sample) // 2):
        return pd.to_datetime(series, errors="coerce", dayfirst=True)
    return pd.to_datetime(series, errors="coerce")


def detect_columns(df: pd.DataFrame, restock: bool = False) -> ColumnMap:
    qty_hints = RESTOCK_QTY_HINTS if restock else QTY_HINTS
    return ColumnMap(
        date=pick_date_column(df),
        sku=pick_column(df, SKU_HINTS),
        device=pick_column(df, DEVICE_HINTS),
        quantity=pick_column(df, qty_hints, numeric=True),
        cost=pick_column(df, COST_HINTS, numeric=True),
    )


def clean_frame(df: pd.DataFrame, cmap: ColumnMap) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = [str(c).strip() for c in cleaned.columns]
    cleaned = cleaned.drop_duplicates()
    for col in cleaned.columns:
        if cleaned[col].dtype == object:
            cleaned[col] = cleaned[col].astype(str).str.strip().replace({"": np.nan, "nan": np.nan})
    if cmap.date:
        cleaned[cmap.date] = parse_datetime_series(cleaned[cmap.date])
    for col in (cmap.quantity, cmap.cost):
        if col:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce")
    return cleaned


def missing_report(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "column": df.columns,
            "missing_count": [int(df[c].isna().sum()) for c in df.columns],
            "missing_pct": [round(float(df[c].isna().mean() * 100), 2) for c in df.columns],
            "dtype": [str(df[c].dtype) for c in df.columns],
        }
    )


def describe_frame(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    numeric = df.select_dtypes(include=[np.number]).describe().T.reset_index(names="column")
    categorical_cols = [c for c in df.columns if c not in df.select_dtypes(include=[np.number]).columns]
    categorical = []
    for col in categorical_cols:
        vc = df[col].astype(str).replace("nan", np.nan).value_counts(dropna=True).head(10)
        categorical.append(
            {
                "column": col,
                "unique_values": int(df[col].nunique(dropna=True)),
                "top_values": "; ".join(f"{k}: {v}" for k, v in vc.items()),
            }
        )
    return {
        "numeric": numeric,
        "categorical": pd.DataFrame(categorical),
    }


def daily_series(df: pd.DataFrame, date_col: str | None, qty_col: str | None, name: str) -> pd.DataFrame:
    if not date_col or not qty_col:
        return pd.DataFrame(columns=["date", name])
    valid = df[[date_col, qty_col]].dropna()
    if valid.empty:
        return pd.DataFrame(columns=["date", name])
    out = (
        valid.assign(date=valid[date_col].dt.floor("D"))
        .groupby("date", as_index=False)[qty_col]
        .sum()
        .rename(columns={qty_col: name})
        .sort_values("date")
    )
    full_index = pd.date_range(out["date"].min(), out["date"].max(), freq="D")
    return out.set_index("date").reindex(full_index, fill_value=0).rename_axis("date").reset_index()


def daily_restock_activity(df: pd.DataFrame, cmap: ColumnMap) -> pd.DataFrame:
    if not cmap.date:
        return pd.DataFrame(columns=["date", "restock_events", "restock_total_cost"])
    cols = [cmap.date] + ([cmap.cost] if cmap.cost else [])
    valid = df[cols].dropna(subset=[cmap.date]).copy()
    if valid.empty:
        return pd.DataFrame(columns=["date", "restock_events", "restock_total_cost"])
    valid["date"] = valid[cmap.date].dt.floor("D")
    grouped = valid.groupby("date").size().reset_index(name="restock_events")
    if cmap.cost:
        spend = valid.groupby("date", as_index=False)[cmap.cost].sum().rename(columns={cmap.cost: "restock_total_cost"})
        grouped = grouped.merge(spend, on="date", how="left")
    else:
        grouped["restock_total_cost"] = np.nan
    full_index = pd.date_range(grouped["date"].min(), grouped["date"].max(), freq="D")
    return grouped.set_index("date").reindex(full_index, fill_value=0).rename_axis("date").reset_index()


def add_time_features(df: pd.DataFrame, date_col: str | None) -> pd.DataFrame:
    if not date_col:
        return pd.DataFrame()
    dates = pd.to_datetime(df[date_col], errors="coerce")
    return pd.DataFrame(
        {
            "date": dates,
            "year": dates.dt.year,
            "month": dates.dt.month,
            "day_of_week": dates.dt.day_name(),
            "week_of_year": dates.dt.isocalendar().week.astype("Int64"),
            "is_weekend": dates.dt.dayofweek >= 5,
        }
    )


def sku_turnover(df: pd.DataFrame, cmap: ColumnMap) -> pd.DataFrame:
    if not cmap.sku or not cmap.quantity:
        return pd.DataFrame()
    group_cols = [cmap.sku]
    result = df.groupby(group_cols, dropna=False)[cmap.quantity].agg(["sum", "mean", "std", "count"]).reset_index()
    result = result.rename(columns={"sum": "total_quantity", "mean": "avg_quantity", "std": "quantity_std", "count": "records"})
    result["coefficient_of_variation"] = result["quantity_std"] / result["avg_quantity"].replace(0, np.nan)
    return result.sort_values("total_quantity", ascending=False)


def sku_monthly_seasonality(df: pd.DataFrame, cmap: ColumnMap) -> pd.DataFrame:
    if not cmap.sku or not cmap.quantity or not cmap.date:
        return pd.DataFrame()
    valid = df[[cmap.sku, cmap.quantity, cmap.date]].dropna()
    if valid.empty:
        return pd.DataFrame()
    valid = valid.assign(month=valid[cmap.date].dt.month)
    monthly = valid.groupby([cmap.sku, "month"], as_index=False)[cmap.quantity].sum()
    totals = monthly.groupby(cmap.sku)[cmap.quantity].transform("sum")
    monthly["share_of_sku_demand"] = monthly[cmap.quantity] / totals.replace(0, np.nan)
    return monthly.sort_values([cmap.sku, "month"])


def device_utilization(df: pd.DataFrame, cmap: ColumnMap) -> pd.DataFrame:
    if not cmap.device or not cmap.quantity:
        return pd.DataFrame()
    out = df.groupby(cmap.device, dropna=False)[cmap.quantity].agg(["sum", "mean", "count"]).reset_index()
    out = out.rename(columns={"sum": "total_quantity", "mean": "avg_quantity_per_record", "count": "activity_records"})
    total = out["total_quantity"].sum()
    out["utilization_share"] = out["total_quantity"] / total if total else np.nan
    return out.sort_values("total_quantity", ascending=False)


def correlation_analysis(inv: pd.DataFrame, restock: pd.DataFrame, inv_map: ColumnMap, restock_map: ColumnMap) -> pd.DataFrame:
    demand = daily_series(inv, inv_map.date, inv_map.quantity, "quantity_dispensed")
    activity = daily_restock_activity(restock, restock_map)
    if demand.empty or activity.empty:
        return pd.DataFrame()
    merged = demand.merge(activity, on="date", how="outer").fillna(0).sort_values("date")
    rows = []
    for rhs in ["restock_events", "restock_total_cost"]:
        if rhs in merged and merged[rhs].nunique() > 1:
            rows.append({"metric_1": "quantity_dispensed", "metric_2": rhs, "correlation": merged["quantity_dispensed"].corr(merged[rhs])})
    return pd.DataFrame(rows)


def forecast_daily(series: pd.DataFrame, value_col: str, horizon: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    if series.empty or len(series) < 8:
        return pd.DataFrame(), pd.DataFrame()
    values = series[value_col].astype(float).reset_index(drop=True)
    dates = pd.to_datetime(series["date"]).reset_index(drop=True)
    test_size = min(max(7, len(values) // 5), 30)
    train = values.iloc[:-test_size]
    test = values.iloc[-test_size:]
    test_dates = dates.iloc[-test_size:]

    preds = []
    history = train.tolist()
    for actual in test:
        if len(history) >= 7:
            pred = float(np.mean(history[-7:]))
        else:
            pred = float(np.mean(history))
        preds.append(max(0.0, pred))
        history.append(float(actual))

    pred_arr = np.array(preds)
    actual_arr = test.to_numpy()
    mae = float(np.mean(np.abs(actual_arr - pred_arr)))
    rmse = float(math.sqrt(np.mean((actual_arr - pred_arr) ** 2)))
    mape = float(np.mean(np.abs((actual_arr - pred_arr) / np.where(actual_arr == 0, np.nan, actual_arr))) * 100)
    metrics = pd.DataFrame(
        [{"model": "7-day rolling average", "test_days": test_size, "MAE": mae, "RMSE": rmse, "MAPE_pct": mape}]
    )

    future_dates = pd.date_range(dates.max() + pd.Timedelta(days=1), periods=horizon, freq="D")
    future_history = values.tolist()
    future_preds = []
    for _ in range(horizon):
        pred = float(np.mean(future_history[-7:])) if len(future_history) >= 7 else float(np.mean(future_history))
        pred = max(0.0, pred)
        future_preds.append(pred)
        future_history.append(pred)
    forecast = pd.DataFrame({"date": future_dates, "forecast_quantity_dispensed": future_preds})
    backtest = pd.DataFrame({"date": test_dates, "actual": actual_arr, "prediction": pred_arr})
    return pd.concat([backtest, forecast], ignore_index=True), metrics


def restocking_recommendations(forecast: pd.DataFrame, top_skus: pd.DataFrame, lead_time_days: int, service_buffer: float) -> pd.DataFrame:
    future = forecast.dropna(subset=["forecast_quantity_dispensed"]) if "forecast_quantity_dispensed" in forecast else pd.DataFrame()
    if future.empty or top_skus.empty:
        return pd.DataFrame()
    daily_total = future["forecast_quantity_dispensed"].mean()
    sku_shares = top_skus.head(20).copy()
    total_qty = sku_shares["total_quantity"].sum()
    if total_qty == 0:
        return pd.DataFrame()
    sku_shares["demand_share"] = sku_shares["total_quantity"] / total_qty
    sku_shares["expected_daily_demand"] = sku_shares["demand_share"] * daily_total
    sku_shares["recommended_reorder_point"] = np.ceil(sku_shares["expected_daily_demand"] * lead_time_days * (1 + service_buffer))
    sku_shares["recommended_weekly_restock_qty"] = np.ceil(sku_shares["expected_daily_demand"] * 7 * (1 + service_buffer))
    return sku_shares


def svg_line(df: pd.DataFrame, date_col: str, value_cols: list[str], title: str, width: int = 920, height: int = 320) -> str:
    if df.empty:
        return "<p>No data available for this chart.</p>"
    plot = df[[date_col] + value_cols].dropna(how="all", subset=value_cols).copy()
    if plot.empty:
        return "<p>No data available for this chart.</p>"
    margin = 42
    xvals = pd.to_datetime(plot[date_col]).map(pd.Timestamp.toordinal).to_numpy(dtype=float)
    yvals = plot[value_cols].to_numpy(dtype=float)
    yvals = yvals[np.isfinite(yvals)]
    if len(yvals) == 0:
        return "<p>No numeric data available for this chart.</p>"
    xmin, xmax = xvals.min(), xvals.max()
    ymin, ymax = min(0.0, yvals.min()), yvals.max()
    if xmax == xmin:
        xmax += 1
    if ymax == ymin:
        ymax += 1

    def sx(x: float) -> float:
        return margin + (x - xmin) / (xmax - xmin) * (width - 2 * margin)

    def sy(y: float) -> float:
        return height - margin - (y - ymin) / (ymax - ymin) * (height - 2 * margin)

    colors = ["#2364aa", "#d95d39", "#3da35d", "#6f4e7c"]
    lines = []
    legend = []
    for i, col in enumerate(value_cols):
        pts = []
        for x, y in zip(xvals, plot[col].to_numpy(dtype=float)):
            if np.isfinite(y):
                pts.append(f"{sx(x):.1f},{sy(y):.1f}")
        if pts:
            color = colors[i % len(colors)]
            lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{color}" stroke-width="2.5"/>')
            legend.append(f'<span><i style="background:{color}"></i>{html.escape(col)}</span>')
    return f"""
    <figure>
      <figcaption>{html.escape(title)}</figcaption>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
        <rect width="{width}" height="{height}" fill="#fff"/>
        <line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#888"/>
        <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height-margin}" stroke="#888"/>
        {"".join(lines)}
        <text x="{margin}" y="24" font-size="13" fill="#444">{html.escape(str(plot[date_col].min().date()))}</text>
        <text x="{width-margin-80}" y="24" font-size="13" fill="#444">{html.escape(str(plot[date_col].max().date()))}</text>
        <text x="{margin}" y="{margin-10}" font-size="13" fill="#444">{ymax:.1f}</text>
      </svg>
      <div class="legend">{"".join(legend)}</div>
    </figure>
    """


def table_html(df: pd.DataFrame, max_rows: int = 10) -> str:
    if df.empty:
        return "<p>No data available.</p>"
    return df.head(max_rows).to_html(index=False, escape=True, classes="data-table")


def write_outputs(outdir: Path, tables: dict[str, pd.DataFrame]) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        if not df.empty:
            df.to_csv(outdir / f"{name}.csv", index=False)


def build_report(outdir: Path, tables: dict[str, pd.DataFrame], charts: dict[str, str], notes: list[str]) -> None:
    sections = []
    for name, df in tables.items():
        pretty = name.replace("_", " ").title()
        sections.append(f"<section><h2>{pretty}</h2>{table_html(df)}</section>")
    report = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Industrial Vending Demand Forecasting Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #20242a; }}
    h1 {{ margin-bottom: 0.2rem; }}
    h2 {{ margin-top: 2rem; border-bottom: 1px solid #d8dde6; padding-bottom: 0.35rem; }}
    .note {{ background: #eef5f7; border-left: 4px solid #2d7d8a; padding: 12px 14px; margin: 16px 0; }}
    .data-table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    .data-table th, .data-table td {{ border: 1px solid #d8dde6; padding: 6px 8px; text-align: left; }}
    .data-table th {{ background: #f3f5f8; }}
    figure {{ margin: 18px 0; }}
    figcaption {{ font-weight: 650; margin-bottom: 6px; }}
    svg {{ max-width: 100%; border: 1px solid #d8dde6; }}
    .legend span {{ margin-right: 16px; font-size: 13px; }}
    .legend i {{ display: inline-block; width: 10px; height: 10px; margin-right: 5px; }}
  </style>
</head>
<body>
  <h1>Industrial Vending Demand Forecasting Report</h1>
  <p>Generated from Inventory_Turnover.csv and Restock_data.csv.</p>
  {"".join(f'<div class="note">{html.escape(note)}</div>' for note in notes)}
  <h2>Time Series Charts</h2>
  {"".join(charts.values())}
  {"".join(sections)}
  <h2>Method</h2>
  <p>The workflow follows standard time-series practice: convert date fields, aggregate by time period, inspect trend and seasonality, create calendar and lag-style features, evaluate a holdout forecast, and translate expected demand into reorder levels. The referenced articles emphasize stationarity, autocorrelation, decomposition, train/test forecasting, and error metrics such as RMSE.</p>
</body>
</html>"""
    (outdir / "vending_demand_forecasting_report.html").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", default="Inventory_Turnover.csv")
    parser.add_argument("--restock", default="Restock_data.csv")
    parser.add_argument("--outdir", default="forecast_outputs")
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--lead-time-days", type=int, default=7)
    parser.add_argument("--service-buffer", type=float, default=0.20)
    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    restock_path = Path(args.restock)
    outdir = Path(args.outdir)
    if not inventory_path.exists() or not restock_path.exists():
        missing = [str(p) for p in (inventory_path, restock_path) if not p.exists()]
        raise FileNotFoundError(f"Missing required file(s): {', '.join(missing)}")

    inv_raw = pd.read_csv(inventory_path)
    restock_raw = pd.read_csv(restock_path)
    inv_map = detect_columns(inv_raw, restock=False)
    restock_map = detect_columns(restock_raw, restock=True)
    inv = clean_frame(inv_raw, inv_map)
    restock = clean_frame(restock_raw, restock_map)

    demand_daily = daily_series(inv, inv_map.date, inv_map.quantity, "quantity_dispensed")
    restock_daily_qty = daily_series(restock, restock_map.date, restock_map.quantity, "quantity_restocked")
    restock_activity = daily_restock_activity(restock, restock_map)
    merged_daily = demand_daily.merge(restock_activity, on="date", how="outer").fillna(0).sort_values("date")
    if not restock_daily_qty.empty:
        merged_daily = merged_daily.merge(restock_daily_qty, on="date", how="left").fillna(0)
    if not merged_daily.empty:
        merged_daily["dispensed_7day_avg"] = merged_daily["quantity_dispensed"].rolling(7, min_periods=1).mean()
        merged_daily["restock_events_7day_avg"] = merged_daily["restock_events"].rolling(7, min_periods=1).mean()
        merged_daily["restock_cost_7day_avg"] = merged_daily["restock_total_cost"].rolling(7, min_periods=1).mean()

    forecast, metrics = forecast_daily(demand_daily, "quantity_dispensed", args.horizon)
    top_skus = sku_turnover(inv, inv_map)
    recommendations = restocking_recommendations(forecast, top_skus, args.lead_time_days, args.service_buffer)

    tables = {
        "inventory_missingness": missing_report(inv),
        "restock_missingness": missing_report(restock),
        "inventory_numeric_statistics": describe_frame(inv)["numeric"],
        "inventory_categorical_statistics": describe_frame(inv)["categorical"],
        "restock_numeric_statistics": describe_frame(restock)["numeric"],
        "restock_categorical_statistics": describe_frame(restock)["categorical"],
        "daily_dispense_restock": merged_daily,
        "top_sku_turnover_and_variability": top_skus,
        "sku_monthly_seasonality": sku_monthly_seasonality(inv, inv_map),
        "device_utilization": device_utilization(inv, inv_map),
        "dispense_restock_correlations": correlation_analysis(inv, restock, inv_map, restock_map),
        "forecast_and_backtest": forecast,
        "forecast_metrics": metrics,
        "restocking_recommendations": recommendations,
        "inventory_time_features_sample": add_time_features(inv, inv_map.date).head(100),
    }

    notes = [
        f"Detected inventory columns: date={inv_map.date}, sku={inv_map.sku}, device={inv_map.device}, quantity={inv_map.quantity}, cost={inv_map.cost}.",
        f"Detected restock columns: date={restock_map.date}, sku={restock_map.sku}, device={restock_map.device}, quantity={restock_map.quantity}, cost={restock_map.cost}.",
        "Forecast model: simple 7-day rolling-average baseline. This is intentionally transparent and works well as a benchmark before trying ARIMA/SARIMA or gradient-boosted lag models.",
    ]
    charts = {
        "daily": svg_line(merged_daily, "date", ["quantity_dispensed", "restock_events"], "Daily Dispensed Quantity and Restock Events"),
        "rolling": svg_line(merged_daily, "date", ["dispensed_7day_avg", "restock_events_7day_avg"], "7-Day Rolling Demand and Restock Event Averages"),
        "forecast": svg_line(forecast, "date", ["actual", "prediction", "forecast_quantity_dispensed"], "Backtest and 30-Day Forecast"),
    }

    write_outputs(outdir, tables)
    build_report(outdir, tables, charts, notes)
    print(f"Analysis complete. Outputs written to: {outdir.resolve()}")


if __name__ == "__main__":
    main()
