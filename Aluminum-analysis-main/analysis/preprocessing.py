from copy import deepcopy
from datetime import date
from functools import lru_cache

import numpy as np
import pandas as pd

from analysis.prediction import cagr, fit_price_level_model, predict_price
from services.aluminum_price_api import load_aluminum_annual_price
from services.ev_sales_api import load_global_ev_sales
from services.komis_live_price_api import fetch_live_aluminum_price
from services.news_adjustment import get_news_adjustment


ALUMINUM_COLOR = "#475569"
EV_COLOR = "#2563EB"
EV_FORECAST_COLOR = "#7DB3FF"
FORECAST_COLOR = "#DC2626"
NEWS_COLOR = "#0F766E"
HISTORICAL_PRICE_YEARS = list(range(2016, 2026))
TRAIN_PRICE_YEARS = list(range(2016, 2024))
VALIDATION_PRICE_YEARS = [2024]
CALIBRATION_PRICE_YEARS = list(range(2016, 2026))


def _server_year() -> int:
    return date.today().year


def _forecast_price_years() -> list[int]:
    start_year = max(_server_year(), max(HISTORICAL_PRICE_YEARS) + 1)
    return list(range(start_year, start_year + 4))


def _next_forecast_year(forecast_price_years: list[int]) -> int:
    next_year = _server_year() + 1
    return next_year if next_year in forecast_price_years else forecast_price_years[0]


def _clean_number(value):
    if value is None or pd.isna(value):
        return None
    return float(value)


def _round(value, digits: int = 2):
    value = _clean_number(value)
    return None if value is None else round(value, digits)


def _chart_payload(
    labels: list[str],
    datasets: list[dict],
    unit: str = "",
    chart_type: str = "line",
    **extra,
) -> dict:
    return {"labels": labels, "datasets": datasets, "unit": unit, "type": chart_type, **extra}


def _corr(frame: pd.DataFrame, left: str, right: str) -> float | None:
    values = frame[[left, right]].dropna()
    if len(values) < 2:
        return None
    return round(float(values[left].corr(values[right])), 3)


def _series_for_years(frame: pd.DataFrame, value_column: str, years: list[int]) -> list[float | None]:
    if frame.empty or value_column not in frame.columns:
        return [None for _ in years]
    values = frame.set_index("year")[value_column].to_dict()
    return [_round(values.get(year), 3) for year in years]


def _lagged_pairs(ev_sales: pd.DataFrame, annual_price: pd.DataFrame) -> pd.DataFrame:
    ev = ev_sales[["year", "ev_sales", "ev_sales_million", "ev_growth_pct"]].rename(columns={"year": "ev_year"})
    ev["price_year"] = ev["ev_year"] - 1
    price = annual_price[annual_price["full_year"]][["year", "aluminum_price", "month_count", "source_file"]].rename(
        columns={"year": "price_year", "source_file": "price_source_file"}
    )
    return pd.merge(price, ev, on="price_year", how="outer").sort_values("price_year").reset_index(drop=True)


def _sales_forecast(ev_sales: pd.DataFrame, end_year: int) -> tuple[pd.DataFrame, dict]:
    window = ev_sales[(ev_sales["year"] >= 2022) & (ev_sales["year"] <= 2025)].sort_values("year")
    if len(window) >= 2:
        start = window.iloc[0]
        end = window.iloc[-1]
    else:
        start = ev_sales.iloc[-2]
        end = ev_sales.iloc[-1]

    growth = cagr(float(start["ev_sales"]), float(end["ev_sales"]), int(end["year"] - start["year"]))
    previous_sales = float(end["ev_sales"])
    rows = []
    for year in range(int(end["year"]) + 1, end_year + 1):
        previous_sales *= 1 + growth
        rows.append(
            {
                "year": year,
                "ev_sales": previous_sales,
                "ev_sales_million": previous_sales / 1_000_000,
                "ev_growth_pct": growth * 100,
                "source_file": "최근 EV 판매량 CAGR 기반 예측",
            }
        )

    metadata = {
        "growth_pct": round(growth * 100, 1),
        "start_year": int(start["year"]),
        "end_year": int(end["year"]),
        "forecast_end_year": int(end_year),
    }
    return pd.DataFrame(rows), metadata


def _validation_predictions(model: dict, pairs: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for price_year in VALIDATION_PRICE_YEARS:
        row = pairs[pairs["price_year"] == price_year]
        if row.empty or pd.isna(row.iloc[0]["ev_sales_million"]):
            continue
        actual_price = _clean_number(row.iloc[0].get("aluminum_price"))
        ev_sales_million = float(row.iloc[0]["ev_sales_million"])
        predicted_price = predict_price(model, ev_sales_million)
        error = predicted_price - actual_price if actual_price is not None else None
        abs_pct_error = abs(error) / actual_price * 100 if actual_price not in (None, 0) else None
        rows.append(
            {
                "year": int(price_year),
                "price_year": int(price_year),
                "ev_year": int(row.iloc[0]["ev_year"]),
                "ev_sales_million": ev_sales_million,
                "actual_price": actual_price,
                "predicted_price": predicted_price,
                "error": error,
                "abs_pct_error": abs_pct_error,
            }
        )

    validation = pd.DataFrame(rows)
    if validation.empty or validation["abs_pct_error"].dropna().empty:
        return validation, {"available": False, "message": "2024 백테스팅 값을 계산하지 못했습니다."}

    errors = validation["error"].dropna()
    abs_pct = validation["abs_pct_error"].dropna()
    return validation, {
        "available": True,
        "mape": round(float(abs_pct.mean()), 1),
        "accuracy": round(max(0.0, 100 - float(abs_pct.mean())), 1),
        "mae": round(float(errors.abs().mean()), 2),
        "rmse": round(float(np.sqrt(np.mean(np.square(errors)))), 2),
        "years": ", ".join(str(int(year)) for year in validation["price_year"].tolist()),
    }


def _future_price_forecast(
    model: dict,
    ev_sales: pd.DataFrame,
    ev_future: pd.DataFrame,
    actual_price: pd.DataFrame,
    news_adjustment: dict,
    price_years: list[int],
) -> pd.DataFrame:
    ev_all = pd.concat([ev_sales, ev_future], ignore_index=True).drop_duplicates("year", keep="last")
    actual_by_year = actual_price.set_index("year")["aluminum_price"].to_dict()
    multiplier = float(news_adjustment["top_category"]["multiplier"])
    rows = []
    for price_year in price_years:
        ev_year = price_year + 1
        row = ev_all[ev_all["year"] == ev_year]
        if row.empty:
            continue
        ev_sales_million = float(row.iloc[0]["ev_sales_million"])
        base_price = predict_price(model, ev_sales_million)
        adjusted_price = base_price * multiplier
        actual = _clean_number(actual_by_year.get(price_year))
        rows.append(
            {
                "year": price_year,
                "price_year": price_year,
                "ev_year": ev_year,
                "ev_sales_million": ev_sales_million,
                "base_predicted_price": base_price,
                "news_adjusted_price": adjusted_price,
                "news_multiplier": multiplier,
                "actual_price": actual,
                "phase": "예측",
            }
        )
    return pd.DataFrame(rows)


def _build_charts(
    pairs: pd.DataFrame,
    ev_sales: pd.DataFrame,
    ev_future: pd.DataFrame,
    validation: pd.DataFrame,
    future_price: pd.DataFrame,
    forecast_price_years: list[int],
) -> dict:
    chart_end_year = max(forecast_price_years)
    price_years = list(range(min(HISTORICAL_PRICE_YEARS), chart_end_year + 1))
    ev_years = list(range(2016, chart_end_year + 2))
    trend_years = list(range(2016, chart_end_year + 1))
    ev_all = pd.concat([ev_sales, ev_future], ignore_index=True).drop_duplicates("year", keep="last")

    prediction_rows = []
    prediction_rows.extend(validation[["price_year", "predicted_price"]].rename(columns={"price_year": "year"}).to_dict("records"))
    prediction_rows.extend(
        future_price[["price_year", "base_predicted_price"]]
        .rename(columns={"price_year": "year", "base_predicted_price": "predicted_price"})
        .to_dict("records")
    )
    prediction_frame = pd.DataFrame(prediction_rows)
    adjusted_frame = (
        future_price[["price_year", "news_adjusted_price"]].rename(columns={"price_year": "year"})
        if not future_price.empty
        else pd.DataFrame(columns=["year", "news_adjusted_price"])
    )

    train_scatter = pairs[pairs["price_year"].isin(TRAIN_PRICE_YEARS)].dropna(subset=["aluminum_price", "ev_sales_million"])
    actual_price_frame = pairs[pairs["price_year"].isin(HISTORICAL_PRICE_YEARS)].rename(columns={"price_year": "year"})
    forecast_line_rows = []
    last_actual = actual_price_frame[actual_price_frame["year"] == max(HISTORICAL_PRICE_YEARS)]
    if not last_actual.empty:
        forecast_line_rows.append(
            {"year": max(HISTORICAL_PRICE_YEARS), "news_adjusted_price": float(last_actual.iloc[0]["aluminum_price"])}
        )
    forecast_line_rows.extend(adjusted_frame.to_dict("records"))
    forecast_line_frame = pd.DataFrame(forecast_line_rows)

    return {
        "price_forecast_chart": _chart_payload(
            [str(year) for year in price_years],
            [
                {
                    "id": "actual_price",
                    "label": "실제 알루미늄 연평균 가격",
                    "data": _series_for_years(pairs.rename(columns={"price_year": "year"}), "aluminum_price", price_years),
                    "color": ALUMINUM_COLOR,
                },
                {
                    "id": "base_price_forecast",
                    "label": "선형회귀 예측 가격",
                    "data": _series_for_years(prediction_frame, "predicted_price", price_years),
                    "color": FORECAST_COLOR,
                    "borderDash": [6, 4],
                },
                {
                    "id": "news_price_forecast",
                    "label": "뉴스 보정 예측 가격",
                    "data": _series_for_years(adjusted_frame, "news_adjusted_price", price_years),
                    "color": NEWS_COLOR,
                    "borderDash": [2, 4],
                },
            ],
            "KOMIS 기준가격",
        ),
        "ev_sales_chart": _chart_payload(
            [str(year) for year in ev_years],
            [
                {
                    "id": "actual_ev_sales",
                    "label": "실제 EV 판매량",
                    "data": _series_for_years(ev_sales, "ev_sales_million", ev_years),
                    "color": EV_COLOR,
                },
                {
                    "id": "forecast_ev_sales",
                    "label": "EV 판매량 예측",
                    "data": _series_for_years(ev_all, "ev_sales_million", ev_years),
                    "color": FORECAST_COLOR,
                    "borderDash": [6, 4],
                },
            ],
            "백만 대",
        ),
        "validation_chart": _chart_payload(
            [str(year) for year in VALIDATION_PRICE_YEARS],
            [
                {
                    "id": "validation_actual_price",
                    "label": "실제 가격",
                    "data": _series_for_years(validation, "actual_price", VALIDATION_PRICE_YEARS),
                    "color": ALUMINUM_COLOR,
                },
                {
                    "id": "validation_predicted_price",
                    "label": "예측 가격",
                    "data": _series_for_years(validation, "predicted_price", VALIDATION_PRICE_YEARS),
                    "color": FORECAST_COLOR,
                },
            ],
            "KOMIS 기준가격",
            "bar",
        ),
        "regression_chart": _chart_payload(
            [str(year) for year in trend_years],
            [
                {
                    "id": "trend_actual_ev",
                    "label": "실제 EV 판매량",
                    "data": _series_for_years(ev_sales, "ev_sales_million", trend_years),
                    "color": "#1D4ED8",
                    "backgroundColor": "#2563EB",
                    "type": "bar",
                    "axis": "y",
                },
                {
                    "id": "trend_forecast_ev",
                    "label": "EV 판매량 예측",
                    "data": _series_for_years(ev_future, "ev_sales_million", trend_years),
                    "color": "#60A5FA",
                    "backgroundColor": "#BFDBFE",
                    "type": "bar",
                    "axis": "y",
                },
                {
                    "id": "trend_actual_price",
                    "label": "실제 알루미늄 가격",
                    "data": _series_for_years(actual_price_frame, "aluminum_price", trend_years),
                    "color": "#DC2626",
                    "type": "line",
                    "axis": "y1",
                },
                {
                    "id": "trend_forecast_price",
                    "label": "알루미늄 가격 예측",
                    "data": _series_for_years(forecast_line_frame, "news_adjusted_price", trend_years),
                    "color": "#F97316",
                    "type": "line",
                    "borderDash": [6, 4],
                    "axis": "y1",
                },
            ],
            "EV 백만 대 / 알루미늄 USD/ton",
            "bar",
            axisTitles={
                "x": "Year",
                "y": "Global EV Sales (BEV+PHEV, Millions)",
                "y1": "LME Aluminum Price (USD/ton)",
            },
            axisColors={"y": "#2563EB", "y1": "#DC2626"},
        ),
    }


def _scenario_control(
    calibrated_model: dict,
    ev_sales: pd.DataFrame,
    ev_future: pd.DataFrame,
    news_adjustment: dict,
    growth_meta: dict,
    forecast_price_years: list[int],
) -> dict:
    latest_ev = ev_sales.sort_values("year").iloc[-1]
    latest_year = int(latest_ev["year"])
    latest_ev_million = float(latest_ev["ev_sales_million"])
    target_ev_year = max(forecast_price_years) + 1
    target_row = ev_future[ev_future["year"] == target_ev_year]
    base_target = float(target_row.iloc[0]["ev_sales_million"]) if not target_row.empty else latest_ev_million

    min_target = round(max(latest_ev_million * 1.05, base_target * 0.45), 1)
    max_target = round(max(base_target * 1.35, min_target + 20), 1)
    def article_payload(article: dict) -> dict:
        return {
            "title": article.get("title", ""),
            "url": article.get("url", "#"),
            "summary": article.get("summary", ""),
            "source": article.get("source", ""),
            "publisher": article.get("publisher", ""),
            "published": article.get("published", ""),
        }

    def issue_summary(category: dict) -> dict:
        multiplier = float(category.get("multiplier", 1))
        if multiplier > 1:
            direction = "상승 압력"
            impact = "기본 회귀 예측값을 상향 보정합니다."
        elif multiplier < 1:
            direction = "하락 압력"
            impact = "기본 회귀 예측값을 하향 보정합니다."
        else:
            direction = "중립"
            impact = "뉴스 보정 없이 기본 회귀 예측값을 유지합니다."

        titles = [article.get("title", "") for article in category.get("articles", [])[:3] if article.get("title")]
        evidence = " / ".join(titles) if titles else "최근 1주 기준으로 표시할 기사 신호가 충분하지 않습니다."
        body = (
            f"{category.get('scenario', '선택한 카테고리의 글로벌 이슈')} 흐름이 알루미늄 수급과 EV 소재 수요에 "
            f"{direction}으로 반영될 가능성이 있습니다."
        )
        return {
            "title": f"{category.get('title', '뉴스 보정')} 이슈 요약",
            "body": body,
            "impact": f"{category.get('formula', 'Price * 1.00')} 기준으로 {impact}",
            "evidence": evidence,
            "source": f"Daum {category.get('daum_count', 0)}건 · Naver {category.get('naver_count', 0)}건",
        }

    raw_categories = list(news_adjustment.get("categories", []))
    top_category = news_adjustment["top_category"]
    if top_category.get("id") not in {category.get("id") for category in raw_categories}:
        raw_categories.insert(0, top_category)

    news_categories = [
        {
            "id": category["id"],
            "title": category["title"],
            "title_en": category["title_en"],
            "scenario": category.get("scenario", ""),
            "weight_range": category.get("weight_range", ""),
            "multiplier": _round(category["multiplier"], 6),
            "formula": category["formula"],
            "score": category.get("score", "0건"),
            "daum_count": category.get("daum_count", 0),
            "naver_count": category.get("naver_count", 0),
            "article_count": category.get("article_count", 0),
            "summary": issue_summary(category),
            "articles": [article_payload(article) for article in category.get("articles", [])],
        }
        for category in raw_categories
    ]
    top_summary = next(
        (category["summary"] for category in news_categories if category["id"] == top_category.get("id")),
        issue_summary(top_category),
    )

    return {
        "latest_ev_year": latest_year,
        "latest_ev_million": _round(latest_ev_million, 3),
        "target_ev_year": target_ev_year,
        "base_target_ev_million": _round(base_target, 3),
        "min_target_ev_million": _round(min_target, 1),
        "max_target_ev_million": _round(max_target, 1),
        "step": 0.5,
        "price_years": forecast_price_years,
        "difference_years": forecast_price_years[1:],
        "reference_price_year": forecast_price_years[0],
        "summary_price_year": _next_forecast_year(forecast_price_years),
        "ev_years": list(range(latest_year + 1, target_ev_year + 1)),
        "forecast_price_year": max(forecast_price_years),
        "intercept": _round(calibrated_model.get("intercept"), 6),
        "slope": _round(calibrated_model.get("slope"), 6),
        "news_multiplier": _round(news_adjustment["top_category"]["multiplier"], 6),
        "news_category": news_adjustment["top_category"]["title"],
        "news_category_id": news_adjustment["top_category"]["id"],
        "news_category_summary": top_summary,
        "news_categories": news_categories,
        "growth_basis": f"{growth_meta['start_year']}~{growth_meta['end_year']}년 CAGR {growth_meta['growth_pct']}%",
    }


@lru_cache(maxsize=1)
def get_dashboard_data() -> dict:
    ev_sales = load_global_ev_sales()
    annual_price = load_aluminum_annual_price()
    full_price = annual_price[annual_price["full_year"]].copy()
    analysis_price = full_price[full_price["year"].isin(HISTORICAL_PRICE_YEARS)].copy()
    pairs = _lagged_pairs(ev_sales, annual_price)
    forecast_price_years = _forecast_price_years()
    forecast_ev_end_year = max(forecast_price_years) + 1

    initial_train = pairs[pairs["price_year"].isin(TRAIN_PRICE_YEARS)].copy()
    initial_model = fit_price_level_model(initial_train)
    validation, validation_metrics = _validation_predictions(initial_model, pairs)

    calibrated_train = pairs[pairs["price_year"].isin(CALIBRATION_PRICE_YEARS)].copy()
    calibrated_model = fit_price_level_model(calibrated_train)

    ev_future, growth_meta = _sales_forecast(ev_sales, forecast_ev_end_year)
    news_adjustment = get_news_adjustment()
    future_price = _future_price_forecast(
        calibrated_model,
        ev_sales,
        ev_future,
        full_price,
        news_adjustment,
        forecast_price_years,
    )
    charts = _build_charts(pairs, ev_sales, ev_future, validation, future_price, forecast_price_years)
    scenario_control = _scenario_control(
        calibrated_model,
        ev_sales,
        ev_future,
        news_adjustment,
        growth_meta,
        forecast_price_years,
    )
    latest_actual_price = analysis_price.sort_values("year").iloc[-1]
    forecast_price_year = max(forecast_price_years)
    forecast_ev_year = forecast_price_year + 1
    next_forecast_year = _next_forecast_year(forecast_price_years)
    future_target = future_price[future_price["price_year"] == forecast_price_year]
    next_future_target = future_price[future_price["price_year"] == next_forecast_year]
    base_target = _round(future_target.iloc[0]["base_predicted_price"], 2) if not future_target.empty else None
    adjusted_target = _round(future_target.iloc[0]["news_adjusted_price"], 2) if not future_target.empty else None
    next_base_target = (
        _round(next_future_target.iloc[0]["base_predicted_price"], 2) if not next_future_target.empty else base_target
    )
    next_adjusted_target = (
        _round(next_future_target.iloc[0]["news_adjusted_price"], 2) if not next_future_target.empty else adjusted_target
    )

    lagged_corr = _corr(pairs[pairs["price_year"].isin(TRAIN_PRICE_YEARS)], "ev_sales_million", "aluminum_price")
    ev_start = 2016
    ev_end = int(ev_sales["year"].max())
    price_start = int(analysis_price["year"].min())
    price_end = int(analysis_price["year"].max())

    return {
        "title": "알루미늄 가격과 전기자동차 판매량 1년 선행 회귀 예측",
        "stats": {
            "latest_price_year": int(latest_actual_price["year"]),
            "latest_price": _round(latest_actual_price["aluminum_price"], 2),
            "recent_ev_cagr_pct": growth_meta["growth_pct"],
            "forecast_year": forecast_price_year,
            "forecast_ev_year": forecast_ev_year,
            "next_forecast_year": next_forecast_year,
            "forecast_ev_target_million": _round(ev_future[ev_future["year"] == forecast_ev_year].iloc[0]["ev_sales_million"], 2)
            if not ev_future[ev_future["year"] == forecast_ev_year].empty
            else None,
            "forecast_price_target": adjusted_target,
            "base_price_target": base_target,
            "next_forecast_price_target": next_adjusted_target,
            "next_base_price_target": next_base_target,
            "validation_mape": validation_metrics.get("mape"),
            "validation_accuracy": validation_metrics.get("accuracy"),
            "lagged_corr": lagged_corr,
            "news_multiplier": _round(news_adjustment["top_category"]["multiplier"], 2),
        },
        "model": {
            "initial_equation": initial_model["equation"],
            "initial_r2": _round(initial_model.get("r2"), 3),
            "initial_price_years": initial_model.get("price_years", ""),
            "initial_ev_years": initial_model.get("ev_years", ""),
            "initial_train_count": initial_model.get("train_count", 0),
            "calibrated_equation": calibrated_model["equation"],
            "calibrated_intercept": _round(calibrated_model.get("intercept"), 6),
            "calibrated_slope": _round(calibrated_model.get("slope"), 6),
            "calibrated_r2": _round(calibrated_model.get("r2"), 3),
            "calibrated_price_years": calibrated_model.get("price_years", ""),
            "calibrated_ev_years": calibrated_model.get("ev_years", ""),
            "calibrated_train_count": calibrated_model.get("train_count", 0),
            "validation": validation_metrics,
            "growth_basis": f"{growth_meta['start_year']}~{growth_meta['end_year']}년 CAGR {growth_meta['growth_pct']}%",
        },
        "data_range": {
            "ev": f"{ev_start}~{ev_end}",
            "price": f"{price_start}~{price_end}",
        },
        "news_adjustment": news_adjustment,
        "scenario_control": scenario_control,
        **charts,
    }


def get_dashboard_view_data() -> dict:
    dashboard = deepcopy(get_dashboard_data())
    live_price = fetch_live_aluminum_price()
    dashboard["live_price"] = live_price
    dashboard["stats"]["komis_live_available"] = live_price.get("available", False)
    dashboard["stats"]["komis_live_price"] = _round(live_price.get("price"), 2)
    dashboard["stats"]["komis_live_date"] = live_price.get("date")
    dashboard["stats"]["komis_live_change"] = _round(live_price.get("change"), 2)
    dashboard["stats"]["komis_live_change_pct"] = _round(live_price.get("change_pct"), 2)
    dashboard["stats"]["komis_live_basis"] = live_price.get("basis", "KOMIS LME CASH · USD/ton")
    dashboard["stats"]["komis_live_server_date"] = live_price.get("server_date")
    return dashboard


def get_mineral_detail(mineral_id: str) -> dict | None:
    if mineral_id != "aluminum":
        return None
    return get_dashboard_view_data()
