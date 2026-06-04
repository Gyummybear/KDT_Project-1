from functools import lru_cache

import pandas as pd

from services.komis_api import load_monthly_price_data


@lru_cache(maxsize=1)
def load_aluminum_annual_price() -> pd.DataFrame:
    monthly, workbook = load_monthly_price_data("aluminum")
    if monthly is None or monthly.empty:
        raise FileNotFoundError("알루미늄 월별 가격 엑셀 파일을 찾지 못했습니다.")

    data = monthly.dropna(subset=["price"]).copy()
    data["year"] = data["period"].map(lambda period: int(period.year))
    annual = (
        data.groupby("year", as_index=False)
        .agg(
            aluminum_price=("price", "mean"),
            month_count=("price", "count"),
            first_month=("month", "min"),
            last_month=("month", "max"),
        )
        .sort_values("year")
        .reset_index(drop=True)
    )
    annual["full_year"] = annual["month_count"] >= 12
    annual["price_change_pct"] = annual["aluminum_price"].pct_change() * 100
    annual["source_file"] = workbook.name if workbook else ""
    return annual
