(function () {
  const registry = new Map();

  function readPayload(id) {
    const node = document.getElementById(id);
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      console.warn("Invalid chart payload", id, error);
      return null;
    }
  }

  function clonePayload(payload) {
    return JSON.parse(JSON.stringify(payload));
  }

  function compactNumber(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
    if (Math.abs(value) >= 1000) return Math.round(value).toLocaleString("ko-KR");
    return Number(value).toLocaleString("ko-KR", { maximumFractionDigits: 1 });
  }

  function chartDataset(payload, dataset) {
    const datasetType = dataset.type || payload.type || "line";
    return {
      id: dataset.id,
      type: datasetType,
      label: dataset.label,
      data: dataset.data,
      yAxisID: dataset.axis || dataset.yAxisID || "y",
      borderColor: dataset.color,
      backgroundColor: dataset.backgroundColor || `${dataset.color || "#2563eb"}22`,
      borderDash: dataset.borderDash || [],
      borderWidth: dataset.borderWidth || (datasetType === "bar" ? 1 : 3),
      pointRadius: datasetType === "bar" ? 0 : 5,
      pointHoverRadius: 7,
      tension: dataset.tension ?? 0.18,
      fill: false,
      order: dataset.order,
      barPercentage: 0.68,
      categoryPercentage: 0.76,
    };
  }

  function drawWithChartJs(canvas, payload) {
    const ctx = canvas.getContext("2d");
    const hasRightAxis = payload.datasets.some((dataset) => (dataset.axis || dataset.yAxisID) === "y1");
    return new Chart(ctx, {
      type: payload.type || "line",
      data: {
        labels: payload.labels,
        datasets: payload.datasets.map((dataset) => chartDataset(payload, dataset)),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { intersect: false, mode: "index" },
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 12, usePointStyle: true },
          },
          tooltip: {
            callbacks: {
              label(context) {
                const unit = payload.unit ? ` ${payload.unit}` : "";
                return `${context.dataset.label}: ${compactNumber(context.parsed.y)}${unit}`;
              },
            },
          },
        },
        scales: {
          x: {
            title: { display: Boolean(payload.axisTitles?.x), text: payload.axisTitles?.x, font: { weight: "bold", size: 14 } },
            grid: { display: false },
            ticks: { maxTicksLimit: 8, autoSkip: true, maxRotation: 0 },
          },
          y: {
            position: "left",
            border: { display: false },
            title: { display: Boolean(payload.axisTitles?.y), text: payload.axisTitles?.y, color: payload.axisColors?.y || "#4F73B3", font: { weight: "bold", size: 14 } },
            grid: { color: "#d9d9d9", borderDash: [5, 5] },
            ticks: { callback: compactNumber, color: payload.axisColors?.y || "#4F73B3" },
          },
          ...(hasRightAxis
            ? {
                y1: {
                  position: "right",
                  border: { display: false },
                  grid: { drawOnChartArea: false },
                  title: { display: Boolean(payload.axisTitles?.y1), text: payload.axisTitles?.y1, color: payload.axisColors?.y1 || "#C84D55", font: { weight: "bold", size: 14 } },
                  ticks: { callback: compactNumber, color: payload.axisColors?.y1 || "#C84D55" },
                },
              }
            : {}),
        },
      },
    });
  }

  function drawFallback(canvas, payload) {
    const ratio = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(rect.width, 320);
    const height = Math.max(rect.height, 240);
    canvas.width = width * ratio;
    canvas.height = height * ratio;
    const ctx = canvas.getContext("2d");
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, height);

    const hasRightAxis = payload.datasets.some((dataset) => (dataset.axis || dataset.yAxisID) === "y1");
    const padding = { top: 24, right: hasRightAxis ? 64 : 22, bottom: 42, left: 64 };
    const plotW = width - padding.left - padding.right;
    const plotH = height - padding.top - padding.bottom;

    function scaleFor(axis) {
      const datasets = payload.datasets.filter((dataset) => (dataset.axis || dataset.yAxisID || "y") === axis);
      const values = datasets.flatMap((dataset) => dataset.data).filter((value) => value !== null && value !== undefined);
      if (!values.length) return { min: 0, max: 1, span: 1 };
      let min = Math.min(...values);
      let max = Math.max(...values);
      if (axis === "y") min = Math.min(0, min);
      const pad = (max - min || Math.max(max, 1)) * 0.08;
      min = axis === "y" ? Math.min(0, min - pad) : min - pad;
      max += pad;
      return { min, max, span: max - min || 1 };
    }

    const leftScale = scaleFor("y");
    const rightScale = scaleFor("y1");

    function yForValue(value, axis) {
      const scale = axis === "y1" ? rightScale : leftScale;
      return padding.top + plotH - ((value - scale.min) / scale.span) * plotH;
    }

    ctx.strokeStyle = "#d9e0e8";
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let i = 0; i <= 4; i += 1) {
      const y = padding.top + (plotH / 4) * i;
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
    }
    ctx.stroke();

    ctx.fillStyle = "#667085";
    ctx.font = "12px Segoe UI, sans-serif";
    ctx.textAlign = "right";
    for (let i = 0; i <= 4; i += 1) {
      const value = leftScale.max - (leftScale.span / 4) * i;
      const y = padding.top + (plotH / 4) * i + 4;
      ctx.fillStyle = payload.axisColors?.y || "#4F73B3";
      ctx.fillText(compactNumber(value), padding.left - 8, y);
    }
    if (hasRightAxis) {
      ctx.textAlign = "left";
      for (let i = 0; i <= 4; i += 1) {
        const value = rightScale.max - (rightScale.span / 4) * i;
        const y = padding.top + (plotH / 4) * i + 4;
        ctx.fillStyle = payload.axisColors?.y1 || "#C84D55";
        ctx.fillText(compactNumber(value), width - padding.right + 8, y);
      }
    }

    const hasBars = payload.datasets.some((dataset) => (dataset.type || payload.type) === "bar");
    if (hasBars) {
      const groupCount = Math.max(payload.labels.length, 1);
      const barDatasets = payload.datasets.filter((dataset) => (dataset.type || payload.type) === "bar");
      const datasetCount = Math.max(barDatasets.length, 1);
      const groupW = plotW / groupCount;
      const barW = (groupW * 0.68) / datasetCount;
      barDatasets.forEach((dataset, datasetIdx) => {
        dataset.data.forEach((value, idx) => {
          if (value === null || value === undefined) return;
          const groupX = padding.left + groupW * idx + groupW * 0.16;
          const x = groupX + datasetIdx * barW;
          const y = yForValue(value, dataset.axis || dataset.yAxisID || "y");
          ctx.fillStyle = value < 0 ? "#dc2626" : dataset.backgroundColor || dataset.color || "#2563eb";
          ctx.fillRect(x, Math.min(y, padding.top + plotH), barW * 0.88, Math.abs(padding.top + plotH - y));
        });
      });
    }

    payload.datasets
      .filter((dataset) => (dataset.type || payload.type) !== "bar")
      .forEach((dataset) => {
        ctx.strokeStyle = dataset.color || "#2563eb";
        if (dataset.borderDash) ctx.setLineDash(dataset.borderDash);
        ctx.lineWidth = dataset.borderWidth || 3;
        ctx.beginPath();
        let started = false;
        dataset.data.forEach((value, idx) => {
          if (value === null || value === undefined) return;
          const x = padding.left + (plotW * idx) / Math.max(dataset.data.length - 1, 1);
          const y = yForValue(value, dataset.axis || dataset.yAxisID || "y");
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        });
        ctx.stroke();
        ctx.setLineDash([]);
      });

    ctx.fillStyle = "#667085";
    ctx.textAlign = "center";
    const labelStep = Math.ceil(payload.labels.length / 6);
    payload.labels.forEach((label, idx) => {
      if (idx % labelStep !== 0 && idx !== payload.labels.length - 1) return;
      const x = padding.left + (plotW * idx) / Math.max(payload.labels.length - 1, 1);
      ctx.fillText(label, x, height - 10);
    });
  }

  function initialiseCharts() {
    document.querySelectorAll("canvas[data-chart-source]").forEach((canvas) => {
      const payload = readPayload(canvas.dataset.chartSource);
      if (!payload) return;
      const id = canvas.dataset.chartSource;
      const existing = registry.get(id);
      if (existing && existing.chart) existing.chart.destroy();
      let chart = null;
      if (window.Chart) {
        chart = drawWithChartJs(canvas, payload);
      } else {
        drawFallback(canvas, payload);
      }
      registry.set(id, { canvas, chart, payload: clonePayload(payload) });
    });
  }

  function updateChart(id, payload) {
    const entry = registry.get(id);
    if (!entry || !payload) return false;
    const nextPayload = clonePayload(payload);
    entry.payload = nextPayload;

    if (entry.chart && window.Chart) {
      entry.chart.config.type = nextPayload.type || "line";
      entry.chart.data.labels = nextPayload.labels;
      entry.chart.data.datasets = nextPayload.datasets.map((dataset) => chartDataset(nextPayload, dataset));
      entry.chart.update();
      return true;
    }

    drawFallback(entry.canvas, nextPayload);
    return true;
  }

  window.DashboardCharts = {
    get(id) {
      const entry = registry.get(id);
      return entry ? clonePayload(entry.payload) : readPayload(id);
    },
    update: updateChart,
  };

  window.addEventListener("DOMContentLoaded", initialiseCharts);
  window.addEventListener("resize", () => {
    if (window.Chart) return;
    registry.forEach((entry) => drawFallback(entry.canvas, entry.payload));
  });
})();
