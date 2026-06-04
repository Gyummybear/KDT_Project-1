(function () {
  const PRICE_CHART_ID = "price-forecast-chart";
  const EV_CHART_ID = "ev-sales-chart";
  const TREND_CHART_ID = "regression-chart";
  const moneyFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 });
  const numberFormat = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 1 });

  function readJson(id) {
    const node = document.getElementById(id);
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      console.warn("Invalid scenario payload", id, error);
      return null;
    }
  }

  function byId(id) {
    return document.getElementById(id);
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function money(value) {
    return `$${moneyFormat.format(value)}`;
  }

  function million(value) {
    return `${numberFormat.format(value)}M`;
  }

  function percent(value) {
    return `${numberFormat.format(value)}%`;
  }

  function setText(id, value) {
    const node = byId(id);
    if (node) node.textContent = value;
  }

  function articleMeta(article) {
    return [article.source, article.publisher, article.published].filter(Boolean).join(" · ");
  }

  function renderNewsArticles(category) {
    const list = byId("scenario-news-list");
    if (!list) return;

    list.innerHTML = "";
    const articles = category.articles || [];
    if (!articles.length) {
      const empty = document.createElement("p");
      empty.className = "muted-text";
      empty.textContent = "최근 1주 기준으로 표시할 뉴스 기사가 없습니다.";
      list.appendChild(empty);
      return;
    }

    articles.forEach((article) => {
      const link = document.createElement("a");
      link.className = "scenario-news-card";
      link.href = article.url || "#";
      link.target = "_blank";
      link.rel = "noopener noreferrer";

      const title = document.createElement("strong");
      title.textContent = article.title || "제목 없음";
      link.appendChild(title);

      const meta = document.createElement("span");
      meta.textContent = articleMeta(article);
      link.appendChild(meta);

      if (article.summary) {
        const summary = document.createElement("small");
        summary.textContent = article.summary;
        link.appendChild(summary);
      }

      list.appendChild(link);
    });
  }

  function updateCategoryDetails(category) {
    if (!category) return;
    const summary = category.summary || {};
    setText("issue-summary-title", summary.title || `${category.title} 이슈 요약`);
    setText("issue-summary-body", summary.body || category.scenario || "");
    setText("issue-summary-impact", summary.impact || category.formula || "");
    setText("issue-summary-evidence", summary.evidence || "");
    setText("issue-summary-source", summary.source || "");
    setText("scenario-news-count", category.score || `${category.article_count || 0}건`);
    renderNewsArticles(category);
  }

  function setBar(id, value, control) {
    const node = byId(id);
    if (!node) return;
    const min = Number(control.min_target_ev_million);
    const max = Number(control.max_target_ev_million);
    const ratio = clamp(((value - min) / Math.max(max - min, 1)) * 100, 5, 100);
    node.style.setProperty("--fill", `${ratio}%`);
  }

  function findDataset(datasets, id, fallback) {
    return datasets.find((dataset) => dataset.id === id) || datasets.find(fallback);
  }

  function scenarioFromTarget(control, targetEvMillion) {
    const latestYear = Number(control.latest_ev_year);
    const targetYear = Number(control.target_ev_year);
    const latestEv = Number(control.latest_ev_million);
    const targetEv = clamp(
      Number(targetEvMillion),
      Number(control.min_target_ev_million),
      Number(control.max_target_ev_million),
    );
    const years = Math.max(targetYear - latestYear, 1);
    const growth = latestEv > 0 ? (targetEv / latestEv) ** (1 / years) - 1 : 0;
    const evByYear = { [latestYear]: latestEv };

    for (let year = latestYear + 1; year <= targetYear; year += 1) {
      evByYear[year] = latestEv * (1 + growth) ** (year - latestYear);
    }

    const priceByYear = {};
    (control.price_years || []).forEach((priceYear) => {
      const evYear = Number(priceYear) + 1;
      const evSalesMillion = evByYear[evYear];
      if (evSalesMillion === undefined) return;
      const basePrice = Number(control.intercept) + Number(control.slope) * evSalesMillion;
      priceByYear[priceYear] = {
        evYear,
        evSalesMillion,
        basePrice,
        adjustedPrice: basePrice * Number(control.news_multiplier),
      };
    });

    const forecast = priceByYear[control.forecast_price_year] || {};
    const summary = priceByYear[control.summary_price_year] || forecast;
    return {
      targetEv,
      growthPct: growth * 100,
      evByYear,
      priceByYear,
      forecastBasePrice: forecast.basePrice || 0,
      forecastAdjustedPrice: forecast.adjustedPrice || 0,
      summaryBasePrice: summary.basePrice || 0,
      summaryAdjustedPrice: summary.adjustedPrice || 0,
    };
  }

  function updatePriceChart(control, scenario) {
    const chartApi = window.DashboardCharts;
    const payload = chartApi && chartApi.get ? chartApi.get(PRICE_CHART_ID) : readJson(PRICE_CHART_ID);
    if (!chartApi || !payload) return;

    const nextPayload = clone(payload);
    const baseDataset = findDataset(
      nextPayload.datasets,
      "base_price_forecast",
      (dataset) => dataset.label.includes("선형회귀"),
    );
    const newsDataset = findDataset(
      nextPayload.datasets,
      "news_price_forecast",
      (dataset) => dataset.label.includes("뉴스"),
    );
    if (!baseDataset || !newsDataset) return;

    (control.price_years || []).forEach((priceYear) => {
      const index = nextPayload.labels.indexOf(String(priceYear));
      const row = scenario.priceByYear[priceYear];
      if (index < 0 || !row) return;
      baseDataset.data[index] = Number(row.basePrice.toFixed(3));
      newsDataset.data[index] = Number(row.adjustedPrice.toFixed(3));
    });

    chartApi.update(PRICE_CHART_ID, nextPayload);
  }

  function updateEvChart(control, scenario) {
    const chartApi = window.DashboardCharts;
    const payload = chartApi && chartApi.get ? chartApi.get(EV_CHART_ID) : readJson(EV_CHART_ID);
    if (!chartApi || !payload) return;

    const nextPayload = clone(payload);
    const forecastDataset = findDataset(
      nextPayload.datasets,
      "forecast_ev_sales",
      (dataset) => dataset.label.includes("예측"),
    );
    if (!forecastDataset) return;

    forecastDataset.data = nextPayload.labels.map((label) => {
      const year = Number(label);
      if (year < Number(control.latest_ev_year)) return null;
      const value = scenario.evByYear[year];
      return value === undefined ? null : Number(value.toFixed(3));
    });

    chartApi.update(EV_CHART_ID, nextPayload);
  }

  function updateTrendChart(control, scenario) {
    const chartApi = window.DashboardCharts;
    const payload = chartApi && chartApi.get ? chartApi.get(TREND_CHART_ID) : readJson(TREND_CHART_ID);
    if (!chartApi || !payload) return;

    const nextPayload = clone(payload);
    const evForecastDataset = findDataset(
      nextPayload.datasets,
      "trend_forecast_ev",
      (dataset) => dataset.label.includes("EV 판매량 예측"),
    );
    const priceForecastDataset = findDataset(
      nextPayload.datasets,
      "trend_forecast_price",
      (dataset) => dataset.label.includes("알루미늄 가격 예측"),
    );

    if (evForecastDataset) {
      evForecastDataset.data = nextPayload.labels.map((label) => {
        const year = Number(label);
        if (year <= Number(control.latest_ev_year)) return null;
        const value = scenario.evByYear[year];
        return value === undefined ? null : Number(value.toFixed(3));
      });
    }

    if (priceForecastDataset) {
      (control.price_years || []).forEach((priceYear) => {
        const index = nextPayload.labels.indexOf(String(priceYear));
        const row = scenario.priceByYear[priceYear];
        if (index < 0 || !row) return;
        priceForecastDataset.data[index] = Number(row.adjustedPrice.toFixed(3));
      });
    }

    chartApi.update(TREND_CHART_ID, nextPayload);
  }

  function updateDifferenceCards(control, scenario) {
    const reference = scenario.priceByYear[control.reference_price_year];
    if (!reference) return;
    (control.difference_years || []).forEach((year) => {
      const row = scenario.priceByYear[year];
      if (!row) return;
      const diff = row.adjustedPrice - reference.adjustedPrice;
      const pct = reference.adjustedPrice ? (diff / reference.adjustedPrice) * 100 : 0;
      setText(`diff-price-${year}`, money(row.adjustedPrice));
      setText(`diff-amount-${year}`, `${diff >= 0 ? "+" : ""}${money(diff)}`);
      setText(`diff-pct-${year}`, `${pct >= 0 ? "+" : ""}${percent(pct)}`);
    });
  }

  function priceBand(value, spread = 0.035) {
    const low = value * (1 - spread);
    const high = value * (1 + spread);
    return `${money(low)} ~ ${money(high)}`;
  }

  function updateScenarioCards(control, scenario) {
    const bull = scenarioFromTarget(control, scenario.targetEv * 1.15);
    const bear = scenarioFromTarget(control, scenario.targetEv * 0.85);

    setText("scenario-bull-ev", `EV ${million(bull.targetEv)} 이상`);
    setText("scenario-bull-price", priceBand(bull.forecastAdjustedPrice));
    setText("scenario-base-ev", `EV ${million(scenario.targetEv)}`);
    setText("scenario-base-price", priceBand(scenario.forecastAdjustedPrice));
    setText("scenario-bear-ev", `EV ${million(bear.targetEv)} 이하`);
    setText("scenario-bear-price", priceBand(bear.forecastAdjustedPrice));

    setBar("scenario-bull-bar", bull.targetEv, control);
    setBar("scenario-base-bar", scenario.targetEv, control);
    setBar("scenario-bear-bar", bear.targetEv, control);
  }

  function updateReadouts(control, scenario) {
    setText("scenario-target-readout", million(scenario.targetEv));
    setText("scenario-cagr-readout", percent(scenario.growthPct));
    setText("scenario-base-readout", money(scenario.summaryBasePrice));
    setText("scenario-adjusted-readout", money(scenario.summaryAdjustedPrice));
    setText("scenario-card-multiplier", Number(control.news_multiplier).toFixed(2));
  }

  function setupControls() {
    const control = readJson("scenario-control");
    const range = byId("ev-target-range");
    const input = byId("ev-target-input");
    const categorySelect = byId("news-category-select");
    if (!control || !range || !input) return;

    const min = Number(control.min_target_ev_million);
    const max = Number(control.max_target_ev_million);
    const base = Number(control.base_target_ev_million);
    const step = Number(control.step || 0.5);

    range.min = min;
    range.max = max;
    range.step = step;
    input.min = min;
    input.max = max;
    input.step = step;
    if (categorySelect) {
      categorySelect.value = control.news_category_id || "";
    }
    updateCategoryDetails(
      (control.news_categories || []).find((category) => category.id === control.news_category_id)
        || (control.news_categories || [])[0],
    );

    function applyTarget(rawValue, source) {
      const value = clamp(Number(rawValue) || base, min, max);
      if (source !== "range") range.value = value;
      if (source !== "input") input.value = value.toFixed(1);

      const scenario = scenarioFromTarget(control, value);
      updateReadouts(control, scenario);
      updateScenarioCards(control, scenario);
      updateDifferenceCards(control, scenario);
      updatePriceChart(control, scenario);
      updateEvChart(control, scenario);
      updateTrendChart(control, scenario);
    }

    range.addEventListener("input", () => applyTarget(range.value, "range"));
    input.addEventListener("input", () => applyTarget(input.value, "input"));
    input.addEventListener("change", () => applyTarget(input.value, "input"));
    if (categorySelect) {
      categorySelect.addEventListener("change", () => {
        const selected = (control.news_categories || []).find((category) => category.id === categorySelect.value);
        if (!selected) return;
        control.news_category_id = selected.id;
        control.news_category = selected.title;
        control.news_multiplier = Number(selected.multiplier);
        updateCategoryDetails(selected);
        applyTarget(range.value, "category");
      });
    }
    applyTarget(base, "initial");
  }

  window.addEventListener("DOMContentLoaded", setupControls);
})();
