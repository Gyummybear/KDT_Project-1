from functools import lru_cache
from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parents[1]
GLOBAL_EV_FILE = ROOT_DIR / "Global_EV_Sales_2012_2025.xlsx"
EV_EXPLORER_FILE = ROOT_DIR / "EV Data Explorer 2026.xlsx"


def _to_year(value) -> int | None:
    try:
        year = int(float(value))
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


def _normalise_sales_frame(frame: pd.DataFrame, source_file: str) -> pd.DataFrame:
    frame = frame.copy()
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame["ev_sales"] = pd.to_numeric(frame["ev_sales"], errors="coerce")
    frame = frame.dropna(subset=["year", "ev_sales"])
    frame["year"] = frame["year"].astype(int)
    frame = frame.groupby("year", as_index=False)["ev_sales"].sum().sort_values("year")
    frame["ev_sales_million"] = frame["ev_sales"] / 1_000_000
    frame["ev_growth_pct"] = frame["ev_sales"].pct_change() * 100
    frame["source_file"] = source_file
    return frame


def _load_global_ev_sales_file(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    workbook = pd.ExcelFile(path)
    sheet = "Global_EV_Sales" if "Global_EV_Sales" in workbook.sheet_names else workbook.sheet_names[0]
    raw = pd.read_excel(path, sheet_name=sheet)
    columns = {str(column).strip().lower(): column for column in raw.columns}
    year_column = columns.get("year")
    sales_column = columns.get("global_ev_sales_units")

    if year_column is None:
        return None
    if sales_column is None:
        sales_candidates = [column for name, column in columns.items() if "sales" in name or "value" in name]
        if not sales_candidates:
            return None
        sales_column = sales_candidates[0]

    frame = raw[[year_column, sales_column]].rename(columns={year_column: "year", sales_column: "ev_sales"})
    return _normalise_sales_frame(frame, path.name)


def _load_country_pivot(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    workbook = pd.ExcelFile(path)
    if "EV sales countries" not in workbook.sheet_names:
        return None

    raw = pd.read_excel(path, sheet_name="EV sales countries", header=None)
    header_index = None
    for idx, value in raw.iloc[:, 0].items():
        if str(value).strip().lower() == "region_country":
            header_index = idx
            break
    if header_index is None:
        return None

    years = [_to_year(value) for value in raw.iloc[header_index, 1:]]
    year_columns = [(col_idx + 1, year) for col_idx, year in enumerate(years) if year is not None]
    if not year_columns:
        return None

    body = raw.iloc[header_index + 1 :].copy()
    total_rows = body[body.iloc[:, 0].astype(str).str.contains("sum|total|합계", case=False, regex=True, na=False)]

    rows = []
    if not total_rows.empty:
        total_row = total_rows.iloc[0]
        for col_idx, year in year_columns:
            rows.append({"year": year, "ev_sales": total_row.iloc[col_idx]})
    else:
        for col_idx, year in year_columns:
            rows.append({"year": year, "ev_sales": pd.to_numeric(body.iloc[:, col_idx], errors="coerce").sum()})

    return _normalise_sales_frame(pd.DataFrame(rows), f"{path.name} / EV sales countries")


def _load_raw_explorer(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None

    workbook = pd.ExcelFile(path)
    if "GEVO_EV_2026" not in workbook.sheet_names:
        return None

    raw = pd.read_excel(path, sheet_name="GEVO_EV_2026")
    required = {"category", "parameter", "mode", "year", "value"}
    if not required.issubset(raw.columns):
        return None

    filtered = raw[
        (raw["category"].astype(str).str.casefold() == "historical")
        & (raw["parameter"].astype(str).str.casefold() == "ev sales")
        & (raw["mode"].astype(str).str.casefold() == "cars")
    ].copy()
    if filtered.empty:
        return None

    frame = filtered.rename(columns={"value": "ev_sales"})[["year", "ev_sales"]]
    return _normalise_sales_frame(frame, f"{path.name} / GEVO_EV_2026")


@lru_cache(maxsize=1)
def load_global_ev_sales() -> pd.DataFrame:
    for loader, path in (
        (_load_global_ev_sales_file, GLOBAL_EV_FILE),
        (_load_country_pivot, EV_EXPLORER_FILE),
        (_load_raw_explorer, EV_EXPLORER_FILE),
    ):
        frame = loader(path)
        if frame is not None and not frame.empty:
            return frame

    raise FileNotFoundError("EV 판매량 엑셀 파일을 찾지 못했습니다.")
