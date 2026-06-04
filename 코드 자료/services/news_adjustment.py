from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from functools import lru_cache
from html import unescape
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen


NEWS_CATEGORIES = [
    {
        "id": "geo_sanctions",
        "title": "전쟁 및 경제 제재",
        "title_en": "Geo / Sanctions",
        "scenario": "주요 수출국 전쟁, 선진국의 특정 국가 거래소 반입 전면 금지 조치",
        "weight_range": "1.10 ~ 1.15 (+10~15%)",
        "multiplier": 1.12,
        "formula": "Price * 1.12",
        "query": "알루미늄 전기차 전쟁 경제 제재 수출 금지 관세",
        "daum_query": "알루미늄 관세 제재 전기차",
    },
    {
        "id": "supply_disruption",
        "title": "대형 공급 차질",
        "title_en": "Supply Disruption",
        "scenario": "세계 1~2위 광산 파업, 자연재해로 인한 붕괴, 핵심 국가의 기술적인 원광 수출 금지",
        "weight_range": "1.05 ~ 1.10 (+5~10%)",
        "multiplier": 1.08,
        "formula": "Price * 1.08",
        "query": "알루미늄 전기차 공급 차질 공장 화재 광산 파업 원광 수출 금지",
        "daum_query": "알루미늄 공급 차질 전기차",
    },
    {
        "id": "tech_demand",
        "title": "신규 기술 수요 폭발",
        "title_en": "Tech Demand",
        "scenario": "AI 전력망 슈퍼사이클 도래, 배터리 신소재 채택률 급증 등 구조적 수요 변화",
        "weight_range": "1.05 ~ 1.08 (+5~8%)",
        "multiplier": 1.06,
        "formula": "Price * 1.06",
        "query": "알루미늄 전기차 AI 전력망 배터리 신소재 수요 급증",
        "daum_query": "알루미늄 전기차 수요 배터리",
    },
    {
        "id": "policy_tariff",
        "title": "보조금 폐지 / 무역 장벽",
        "title_en": "Policy / Tariff",
        "scenario": "중국 보조금 완전 폐지, EU/미국의 고율 관세 부과, IRA 같은 보호무역주의",
        "weight_range": "0.90 ~ 0.95 (-5~10%)",
        "multiplier": 0.92,
        "formula": "Price * 0.92",
        "query": "알루미늄 전기차 보조금 폐지 무역 장벽 관세 IRA",
        "daum_query": "전기차 보조금 관세 알루미늄",
    },
    {
        "id": "tech_shift_chasm",
        "title": "기술 퇴출 및 수요 침체",
        "title_en": "Tech Shift / Chasm",
        "scenario": "캐즘 이론에 의한 전방 산업 수요 정체, 특정 광물 배제 선언",
        "weight_range": "0.80 ~ 0.85 (-15~20%)",
        "multiplier": 0.83,
        "formula": "Price * 0.83",
        "query": "전기차 캐즘 알루미늄 수요 침체 기술 전환 판매 부진",
        "daum_query": "전기차 캐즘 알루미늄",
    },
    {
        "id": "macro_crisis",
        "title": "글로벌 경제/금융 위기",
        "title_en": "Macro Crisis",
        "scenario": "글로벌 팬데믹, 공장 셧다운, 대형 은행 파산, 미국발 금융위기",
        "weight_range": "0.85 ~ 0.90 (-10~15%)",
        "multiplier": 0.88,
        "formula": "Price * 0.88",
        "query": "알루미늄 전기차 글로벌 금융 위기 경기 침체 공장 셧다운",
        "daum_query": "알루미늄 경기 침체 전기차",
    },
]


def _fetch_text(url: str, timeout: float = 3.0) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def _clean_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def _dedupe_articles(articles: list[dict], limit: int = 10) -> list[dict]:
    seen = set()
    unique = []
    for article in articles:
        key = article.get("url") or article.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(article)
        if len(unique) >= limit:
            break
    return unique


def _daum_news_articles(query: str, since: date, today: date) -> tuple[list[dict], str]:
    url = f"https://search.daum.net/search?w=news&q={quote_plus(query)}&period=w"
    try:
        html = _fetch_text(url)
    except Exception:
        return [], url

    blocks = re.split(r'<li\s+data-docid="[^"]+"', html)[1:]
    articles = []
    for block in blocks:
        title_match = re.search(
            r'<div class="item-title">.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
            block,
            flags=re.S,
        )
        if not title_match:
            continue
        publisher_match = re.search(r'<strong class="tit_item" title="([^"]+)"', block)
        summary_match = re.search(r'<p class="conts-desc[^"]*">\s*<a[^>]*>(.*?)</a>', block, flags=re.S)
        date_match = re.search(r'<span class="gem-subinfo">([^<]+)</span>', block)
        articles.append(
            {
                "source": "Daum",
                "publisher": _clean_html(publisher_match.group(1)) if publisher_match else "Daum News",
                "title": _clean_html(title_match.group(2)),
                "url": unescape(title_match.group(1)).replace("http://", "https://"),
                "summary": _clean_html(summary_match.group(1)) if summary_match else "",
                "published": _clean_html(date_match.group(1)) if date_match else "",
            }
        )
    if not articles:
        for match in re.finditer(r'href="(https?://v\.daum\.net/v/[^"]+)"[^>]*>.*?<img[^>]+alt="([^"]+)"', html, flags=re.S):
            articles.append(
                {
                    "source": "Daum",
                    "publisher": "Daum News",
                    "title": _clean_html(match.group(2)),
                    "url": unescape(match.group(1)).replace("http://", "https://"),
                    "summary": "",
                    "published": "",
                }
            )
    return _dedupe_articles(articles), url


def _naver_news_articles(query: str, since: date, today: date) -> tuple[list[dict], str]:
    ds = since.strftime("%Y.%m.%d")
    de = today.strftime("%Y.%m.%d")
    url = (
        "https://search.naver.com/search.naver?where=news&sm=tab_opt&sort=0&pd=3"
        f"&ds={ds}&de={de}&query={quote_plus(query)}"
    )
    try:
        html = _fetch_text(url)
    except Exception:
        return [], url

    articles = []
    for match in re.finditer(
        r'<a[^>]+class="news_tit"[^>]+href="([^"]+)"[^>]+title="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.S,
    ):
        start = max(0, match.start() - 700)
        end = min(len(html), match.end() + 900)
        block = html[start:end]
        publisher_match = re.search(r'<a[^>]+class="info press"[^>]*>(.*?)</a>', block, flags=re.S)
        summary_match = re.search(r'<a[^>]+class="api_txt_lines dsc_txt_wrap"[^>]*>(.*?)</a>', block, flags=re.S)
        date_match = re.search(r'<span class="info">([^<]+)</span>', block)
        articles.append(
            {
                "source": "Naver",
                "publisher": _clean_html(publisher_match.group(1)) if publisher_match else "Naver News",
                "title": _clean_html(match.group(2) or match.group(3)),
                "url": unescape(match.group(1)),
                "summary": _clean_html(summary_match.group(1)) if summary_match else "",
                "published": _clean_html(date_match.group(1)) if date_match else "",
            }
        )
    if not articles:
        for match in re.finditer(
            r'\},"title":"(.*?)","titleHref":"(https?://[^"]+)","type":"searchBasic"',
            html,
            flags=re.S,
        ):
            start = max(0, match.start() - 1400)
            block = html[start : match.end()]
            content_match = re.search(r'"content":"(.*?)","contentHref"', block, flags=re.S)
            publisher_matches = re.findall(r'"sourceProfile":\{.*?"title":"(.*?)"', block, flags=re.S)
            articles.append(
                {
                    "source": "Naver",
                    "publisher": _clean_html(publisher_matches[-1]) if publisher_matches else "Naver News",
                    "title": _clean_html(match.group(1)),
                    "url": unescape(match.group(2)).replace("\\/", "/"),
                    "summary": _clean_html(content_match.group(1)) if content_match else "",
                    "published": "",
                }
            )
    return _dedupe_articles(articles), url


def _score_category(category: dict, today: date, since: date) -> dict:
    daum_articles, daum_url = _daum_news_articles(category.get("daum_query", category["query"]), since, today)
    naver_articles, naver_url = _naver_news_articles(category["query"], since, today)
    articles = _dedupe_articles(daum_articles + naver_articles, limit=12)
    daum_count = len(daum_articles)
    naver_count = len(naver_articles)
    total = daum_count + naver_count
    return {
        **category,
        "daum_count": daum_count,
        "naver_count": naver_count,
        "article_count": total,
        "daum_url": daum_url,
        "naver_url": naver_url,
        "articles": articles,
        "score": f"{total}건",
    }


@lru_cache(maxsize=8)
def get_news_adjustment(reference_date: str | None = None) -> dict:
    today = datetime.strptime(reference_date, "%Y-%m-%d").date() if reference_date else date.today()
    since = today - timedelta(days=7)
    ranked = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_score_category, category, today, since) for category in NEWS_CATEGORIES]
        for future in as_completed(futures):
            ranked.append(future.result())

    ranked = sorted(ranked, key=lambda item: item["article_count"], reverse=True)
    top = ranked[0] if ranked and ranked[0]["article_count"] > 0 else None
    if top is None:
        top = {
            "id": "none",
            "title": "뉴스 보정 없음",
            "title_en": "No Live Signal",
            "scenario": "최근 1주 뉴스 데이터를 불러오지 못해 보정치를 적용하지 않았습니다.",
            "weight_range": "1.00",
            "multiplier": 1.0,
            "formula": "Price * 1.00",
            "query": "",
            "daum_count": 0,
            "naver_count": 0,
            "article_count": 0,
            "articles": [],
            "score": "0건",
        }

    return {
        "reference_date": today.isoformat(),
        "since_date": since.isoformat(),
        "top_category": top,
        "categories": ranked,
        "sources": ["Daum News Search", "Naver News Search"],
    }
