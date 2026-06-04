from pathlib import Path
import warnings

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
PRICE_DATA_DIR = ROOT_DIR / "data" / "mineral_prices"

MINERAL_FILE_HINTS = {
    "iron": ["철"],
    "copper": ["동", "구리"],
    "aluminum": ["알루미늄"],
    "nickel": ["니켈"],
    "lithium": ["리튬"],
    "cobalt": ["코발트"],
}


def _format_quarter(period: pd.Period) -> str:
    return f"{period.year} Q{period.quarter}"


def _is_excel_workbook(path: Path) -> bool:
    return path.suffix.lower() == ".xlsx" and not path.name.startswith("~$")


def _candidate_workbooks(mineral_id: str) -> list[Path]:
    hints = MINERAL_FILE_HINTS.get(mineral_id, [mineral_id])
    candidates: list[Path] = []

    mineral_dir = PRICE_DATA_DIR / mineral_id
    if mineral_dir.exists():
        candidates.extend(path for path in mineral_dir.glob("*.xlsx") if _is_excel_workbook(path))

    if PRICE_DATA_DIR.exists():
        for hint in hints:
            candidates.extend(path for path in PRICE_DATA_DIR.glob(f"**/*{hint}*_월간.xlsx") if _is_excel_workbook(path))

    for hint in hints:
        candidates.extend(path for path in ROOT_DIR.glob(f"*{hint}*_월간.xlsx") if _is_excel_workbook(path))

    unique = {path.resolve(): path for path in candidates}
    return sorted(unique.values(), key=lambda path: path.stat().st_mtime, reverse=True)


def find_price_workbook(mineral_id: str) -> Path | None:
    candidates = _candidate_workbooks(mineral_id)
    return candidates[0] if candidates else None


def discover_price_workbooks() -> dict[str, Path]:
    return {
        mineral_id: workbook
        for mineral_id in MINERAL_FILE_HINTS
        if (workbook := find_price_workbook(mineral_id)) is not None
    }


def load_monthly_price_data(mineral_id: str) -> tuple[pd.DataFrame | None, Path | None]:
    workbook = find_price_workbook(mineral_id)
    if workbook is None:
        return None, None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        raw = pd.read_excel(workbook, sheet_name=0, header=2)

    data = raw.rename(
        columns={
            "기준일": "month_code",
            "기준가격": "price",
            "최저가": "low_price",
            "최고가": "high_price",
            "전일대비등락가": "daily_change",
            "전일대비등락비율": "daily_change_rate",
            "LME재고량": "stock",
        }
    )
    required = {"month_code", "price"}
    if not required.issubset(data.columns):
        missing = ", ".join(sorted(required - set(data.columns)))
        raise ValueError(f"{workbook.name} 파일에 필수 컬럼이 없습니다: {missing}")

    data["month_code"] = data["month_code"].astype(str).str.replace(r"\.0$", "", regex=True).str[:6]
    data = data[data["month_code"].str.match(r"^\d{6}$", na=False)].copy()
    data["date"] = pd.to_datetime(data["month_code"] + "01", format="%Y%m%d", errors="coerce")

    numeric_columns = ["price", "low_price", "high_price", "daily_change", "daily_change_rate", "stock"]
    for column in numeric_columns:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")

    data = data.dropna(subset=["date", "price"]).sort_values("date").reset_index(drop=True)
    data["period"] = data["date"].dt.to_period("M")
    data["month"] = data["period"].astype(str)
    data["quarter_period"] = data["date"].dt.to_period("Q")
    data["quarter"] = data["quarter_period"].map(_format_quarter)
    data["change_rate"] = data["price"].pct_change() * 100
    data["source_file"] = workbook.name
    return data, workbook


def load_quarterly_price_data(mineral_id: str) -> tuple[pd.DataFrame | None, Path | None]:
    monthly, workbook = load_monthly_price_data(mineral_id)
    if monthly is None:
        return None, None

    aggregations = {"price": ("price", "mean"), "month_count": ("price", "count")}
    if "stock" in monthly.columns:
        aggregations["stock"] = ("stock", "mean")

    quarterly = monthly.groupby("quarter_period", as_index=False).agg(**aggregations).sort_values("quarter_period")
    quarterly = quarterly.rename(columns={"quarter_period": "period"})
    quarterly["date"] = quarterly["period"].dt.to_timestamp(how="end").dt.date.astype(str)
    quarterly["quarter"] = quarterly["period"].map(_format_quarter)
    quarterly["change_rate"] = quarterly["price"].pct_change() * 100
    quarterly["source_file"] = workbook.name if workbook else ""
    return quarterly, workbook


def load_copper_price_data():
    """Compatibility helper for older imports."""
    return load_quarterly_price_data("copper")[0]
