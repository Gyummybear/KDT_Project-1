import numpy as np
import pandas as pd


def cagr(start_value: float, end_value: float, years: int) -> float:
    if start_value <= 0 or years <= 0:
        return 0.0
    return (end_value / start_value) ** (1 / years) - 1


def fit_price_level_model(train: pd.DataFrame) -> dict:
    values = train[["price_year", "ev_year", "ev_sales_million", "aluminum_price"]].dropna().copy()
    if len(values) < 2:
        return {
            "available": False,
            "message": "학습 가능한 연도 수가 부족합니다.",
            "equation": "학습 불가",
            "train_count": int(len(values)),
        }

    x = values["ev_sales_million"].astype(float).to_numpy()
    y = values["aluminum_price"].astype(float).to_numpy()
    design = np.column_stack([np.ones(len(x)), x])
    intercept, slope = np.linalg.lstsq(design, y, rcond=None)[0]
    fitted = intercept + slope * x
    residual = np.sum((y - fitted) ** 2)
    total = np.sum((y - y.mean()) ** 2)
    r2 = 1 - residual / total if total else 0.0

    sign = "+" if slope >= 0 else "-"
    return {
        "available": True,
        "intercept": float(intercept),
        "slope": float(slope),
        "r2": float(r2),
        "equation": f"알루미늄 가격 = {intercept:.2f} {sign} {abs(slope):.2f} × EV 판매량(백만 대)",
        "train_count": int(len(values)),
        "price_years": f"{int(values['price_year'].min())}~{int(values['price_year'].max())}",
        "ev_years": f"{int(values['ev_year'].min())}~{int(values['ev_year'].max())}",
    }


def predict_price(model: dict, ev_sales_million: float) -> float:
    if not model.get("available"):
        return 0.0
    return float(model["intercept"] + model["slope"] * ev_sales_million)
