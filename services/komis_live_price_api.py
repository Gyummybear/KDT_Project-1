from __future__ import annotations

from datetime import datetime
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo


KOMIS_ALUMINUM_CODE = "MNRL0009"
KOMIS_LME_CASH_CRITERION = "495"
KOMIS_PRICE_URL = "https://www.komis.or.kr/Komis/RsrcPrice/ajax/getMnrlPrcByMnrkndUnqCd"
SERVER_TIMEZONE = ZoneInfo("Asia/Seoul")


def _server_now() -> datetime:
    return datetime.now(SERVER_TIMEZONE)


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def _format_date(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def fetch_live_aluminum_price(timeout: float = 4.0) -> dict:
    server_now = _server_now()
    server_date = server_now.date()
    year = server_date.year
    body = urlencode(
        {
            "srchMnrkndUnqCd": KOMIS_ALUMINUM_CODE,
            "srchPrcCrtr": KOMIS_LME_CASH_CRITERION,
            "srchAvgOpt": "DAY",
            "srchField": "year",
            "srchStartDate": str(year),
            "srchEndDate": str(year),
            "lmeInvt": "Y",
            "_": str(int(server_now.timestamp())),
        }
    ).encode("utf-8")
    request = Request(
        KOMIS_PRICE_URL,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://www.komis.or.kr/Komis/RsrcPrice/BaseMetals",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception as error:
        return {
            "available": False,
            "price": None,
            "date": None,
            "change": None,
            "change_pct": None,
            "basis": "KOMIS LME CASH · USD/ton",
            "source": "KOMIS 가격정보",
            "server_date": server_date.isoformat(),
            "error": str(error),
        }

    std_map = payload.get("dataAvg", {}).get("stdMap", {})
    day = std_map.get("DAY", {})
    info = std_map.get("INFO", {})
    current = std_map.get("CRTRYMD", {})
    price = _to_float(day.get("cmercPrc", current.get("cmercPrc")))
    price_date = _format_date(day.get("crtrYmd", current.get("crtrYmd")))
    unit = f"{info.get('prcUnitCdNm', 'USD')}/{info.get('weigUnitCd', 'ton')}"
    criterion = info.get("prcCrtr", "LME CASH")

    return {
        "available": price is not None,
        "price": price,
        "date": price_date,
        "change": _to_float(day.get("flctnPrc")),
        "change_pct": _to_float(day.get("flctnPrcnt")),
        "basis": f"{criterion} · {unit}",
        "source": "KOMIS 가격정보",
        "server_date": server_date.isoformat(),
        "error": None,
    }
