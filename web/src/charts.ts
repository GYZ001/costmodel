import type { EChartsCoreOption } from "echarts/core";
import { escapeHtml, palette } from "./lib";

/** "label: value" in the reader's language (the separator differs, e.g. "：" in Chinese). */
export type KV = (label: string, value: string) => string;

export interface RankItem {
  id: string;
  name: string;
  value: number;
  highlight: boolean;
  secondary?: number | null;
  tip: string[]; // extra tooltip lines (plain text, escaped here)
  table?: string[]; // fuller lines for the data-table twin (defaults to tip)
}

const AXIS_FONT = 12;
const FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, "Noto Sans", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Apple SD Gothic Neo", "Malgun Gothic", "Noto Sans Arabic", "Noto Sans Devanagari", sans-serif';

function baseText(p: ReturnType<typeof palette>) {
  return { color: p.ink2, fontSize: AXIS_FONT, fontFamily: FONT };
}

/** Left margin wide enough for the longest category label (CJK glyphs ≈ 1 em, others ≈ 0.6 em). */
function labelWidth(names: string[]): number {
  const w = (s: string) => [...s].reduce((acc, ch) => acc + (ch.charCodeAt(0) > 0x2e80 ? AXIS_FONT : AXIS_FONT * 0.62), 0);
  return Math.ceil(Math.max(40, ...names.map(w))) + 14;
}

function categoryAxis(p: ReturnType<typeof palette>, names: string[], highlighted: (n: string) => boolean, inverse = false) {
  return {
    type: "category" as const,
    data: names,
    inverse,
    triggerEvent: true,
    axisLine: { lineStyle: { color: p.axis } },
    axisTick: { show: false },
    axisLabel: {
      ...baseText(p),
      formatter: (n: string) => (highlighted(n) ? `{b|${n}}` : `{n|${n}}`),
      rich: {
        b: { color: p.ink, fontWeight: 600, fontSize: AXIS_FONT, fontFamily: FONT },
        n: { color: p.ink2, fontSize: AXIS_FONT, fontFamily: FONT },
      },
    },
  };
}

function tooltipBox(p: ReturnType<typeof palette>) {
  return {
    backgroundColor: p.surface,
    borderColor: p.grid,
    borderWidth: 1,
    padding: [8, 10],
    textStyle: { color: p.ink, fontSize: 12.5 },
    extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,.12); border-radius: 8px; max-width: 360px; white-space: normal;",
  };
}

/** Horizontal ranking: one bar per economy (highlighted ones in the accent hue, others de-emphasised),
 *  optional secondary dot (e.g. median). Values are drawn on a log axis when they span > 30×. */
export function rankingOption(opts: {
  items: RankItem[];
  valueName: string;
  secondaryName?: string;
  format: (v: number) => string;
  kv: KV;
}): EChartsCoreOption {
  const p = palette();
  const items = [...opts.items].sort((a, b) => a.value - b.value); // bottom→top in category axis
  const names = items.map((i) => i.name);
  const byName = new Map(items.map((i) => [i.name, i]));
  // With no economy in focus every bar is drawn alike (and labelled when there are few).
  const anyFocus = items.some((i) => i.highlight);
  const labelled = (i: RankItem | undefined) => !!i && (i.highlight || (!anyFocus && items.length <= 25));
  return {
    animation: false,
    grid: { left: labelWidth(names), right: 72, top: 8, bottom: 28, containLabel: false },
    xAxis: {
      type: "value",
      min: 0,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: p.grid, width: 1 } },
      axisLabel: { ...baseText(p), formatter: (v: number) => opts.format(v) },
    },
    yAxis: categoryAxis(p, names, (n) => !!byName.get(n)?.highlight),
    tooltip: {
      ...tooltipBox(p),
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: p.grid, opacity: 0.35 } },
      formatter: (params: { name: string }[]) => {
        const it = byName.get(params[0].name);
        if (!it) return "";
        const sec = it.secondary != null && opts.secondaryName
          ? `<div>${escapeHtml(opts.kv(opts.secondaryName, opts.format(it.secondary)))}</div>` : "";
        return `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(it.name)}</div>` +
          `<div><b>${escapeHtml(opts.kv(opts.valueName, opts.format(it.value)))}</b></div>${sec}` +
          it.tip.map((t) => `<div style="color:${p.ink2}">${escapeHtml(t)}</div>`).join("");
      },
    },
    series: [
      {
        name: opts.valueName,
        type: "bar",
        barMaxWidth: 14,
        barCategoryGap: "30%",
        data: items.map((i) => ({
          value: i.value,
          itemStyle: { color: i.highlight || !anyFocus ? p.accent : p.deemph, borderRadius: [0, 4, 4, 0] },
        })),
        label: {
          show: true,
          position: "right",
          color: p.ink2,
          fontSize: 11.5,
          formatter: (d: { name: string; value: number }) => (labelled(byName.get(d.name)) ? opts.format(d.value) : ""),
        },
      },
      ...(opts.secondaryName
        ? [
            {
              name: opts.secondaryName,
              type: "scatter",
              symbolSize: 8,
              itemStyle: { color: p.series[1], borderColor: p.surface, borderWidth: 2 },
              data: items.map((i) => (i.secondary != null && i.secondary > 0 ? i.secondary : null)),
              z: 3,
            },
          ]
        : []),
    ],
  };
}

export function rankingHeight(n: number): number {
  return Math.max(160, n * 20 + 56);
}

/** Dumbbell on a log axis: two values per economy in the same unit (e.g. a wage at market
 *  exchange rates and at purchasing power parity). */
export function dumbbellOption(opts: {
  rows: { name: string; a: number; b: number; highlight: boolean; tip: string[] }[];
  aName: string;
  bName: string;
  format: (v: number) => string;
  kv: KV;
}): EChartsCoreOption {
  const p = palette();
  const rows = [...opts.rows].sort((x, y) => x.b - y.b);
  const names = rows.map((r) => r.name);
  const byName = new Map(rows.map((r) => [r.name, r]));
  const fmtv = opts.format;
  return {
    animation: false,
    grid: { left: labelWidth(names), right: 24, top: 8, bottom: 28, containLabel: false },
    xAxis: {
      type: "log",
      logBase: 10,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: p.grid } },
      axisLabel: { ...baseText(p), formatter: (v: number) => fmtv(v) },
    },
    yAxis: categoryAxis(p, names, (n) => !!byName.get(n)?.highlight),
    tooltip: {
      ...tooltipBox(p),
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: p.grid, opacity: 0.35 } },
      formatter: (params: { name: string }[]) => {
        const r = byName.get(params[0].name);
        if (!r) return "";
        return `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(r.name)}</div>` +
          `<div>${escapeHtml(opts.kv(opts.aName, fmtv(r.a)))}</div>` +
          `<div><b>${escapeHtml(opts.kv(opts.bName, fmtv(r.b)))}</b></div>` +
          r.tip.map((t) => `<div style="color:${p.ink2}">${escapeHtml(t)}</div>`).join("");
      },
    },
    series: [
      {
        type: "custom",
        name: "",
        silent: true,
        renderItem: (_params: unknown, api: any) => {
          const i = api.value(0);
          const s = api.coord([api.value(1), i]);
          const e = api.coord([api.value(2), i]);
          return { type: "line", shape: { x1: s[0], y1: s[1], x2: e[0], y2: e[1] }, style: { stroke: p.axis, lineWidth: 2 } };
        },
        encode: { x: [1, 2], y: 0 },
        data: rows.map((r, i) => [i, r.a, r.b]),
        z: 1,
      },
      {
        name: opts.aName,
        type: "scatter",
        symbolSize: 9,
        itemStyle: { color: p.deemph, borderColor: p.surface, borderWidth: 2 },
        data: rows.map((r) => r.a),
        z: 2,
      },
      {
        name: opts.bName,
        type: "scatter",
        symbolSize: 9,
        itemStyle: { color: p.accent, borderColor: p.surface, borderWidth: 2 },
        data: rows.map((r) => r.b),
        z: 3,
      },
    ],
  };
}

/** Horizontal stacked bars (part-to-whole) with a 2px surface gap between segments. */
export function stackedOption(opts: {
  rows: { name: string; parts: number[]; highlight: boolean; total: number; tip: string[] }[];
  partNames: string[];
  format: (v: number) => string;
  totalName: string;
  kv: KV;
}): EChartsCoreOption {
  const p = palette();
  const rows = [...opts.rows].sort((a, b) => b.total - a.total);
  const names = rows.map((r) => r.name);
  const byName = new Map(rows.map((r) => [r.name, r]));
  return {
    animation: false,
    grid: { left: labelWidth(names), right: 64, top: 8, bottom: 28, containLabel: false },
    xAxis: {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: p.grid } },
      axisLabel: { ...baseText(p), formatter: (v: number) => opts.format(v) },
    },
    yAxis: categoryAxis(p, names, (n) => !!byName.get(n)?.highlight, true),
    tooltip: {
      ...tooltipBox(p),
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: p.grid, opacity: 0.35 } },
      formatter: (params: { name: string }[]) => {
        const r = byName.get(params[0].name);
        if (!r) return "";
        const lines = opts.partNames
          .map((pn, i) => `<div><span style="display:inline-block;width:14px;height:2px;background:${p.series[i]};vertical-align:4px;margin-inline-end:6px"></span>${escapeHtml(opts.kv(pn, opts.format(r.parts[i])))}</div>`)
          .join("");
        return `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(r.name)}</div><div><b>${escapeHtml(opts.kv(opts.totalName, opts.format(r.total)))}</b></div>${lines}` +
          r.tip.map((t) => `<div style="color:${p.ink2}">${escapeHtml(t)}</div>`).join("");
      },
    },
    series: opts.partNames.map((pn, i) => ({
      name: pn,
      type: "bar",
      stack: "total",
      barMaxWidth: 14,
      barCategoryGap: "30%",
      itemStyle: { color: p.series[i], borderColor: p.surface, borderWidth: 1 },
      data: rows.map((r) => r.parts[i]),
    })),
  };
}

/** Heatmap of price levels relative to a base (ratio 1 = same as the base), on a diverging
 *  blue↔red scale of the log ratio. */
export function heatmapOption(opts: {
  rows: string[];
  cols: string[];
  values: [number, number, number | null][]; // col, row, ratio to the base
  highlightRows: Set<string>;
  label: (ratio: number) => string;
  tip: (ratio: number) => string;
}): EChartsCoreOption {
  const p = palette();
  const data = opts.values.filter((v) => v[2] !== null).map(([c, r, v]) => [c, r, Math.log2(v as number), v]);
  return {
    animation: false,
    grid: { left: labelWidth(opts.rows), right: 8, top: 48, bottom: 8, containLabel: false },
    xAxis: {
      type: "category",
      data: opts.cols,
      position: "top",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { ...baseText(p), interval: 0, rotate: 0, width: 66, overflow: "break", lineHeight: 14 },
      splitArea: { show: false },
    },
    yAxis: { ...categoryAxis(p, opts.rows, (n) => opts.highlightRows.has(n), true), axisLine: { show: false } },
    visualMap: {
      show: false,
      dimension: 2,
      min: -1.5,
      max: 1.5,
      inRange: { color: [p.divNeg, p.divMid, p.divPos] },
    },
    tooltip: {
      ...tooltipBox(p),
      formatter: (d: { data: [number, number, number, number] }) => {
        const [c, r, , v] = d.data;
        return `<div style="font-weight:600">${escapeHtml(opts.rows[r])} · ${escapeHtml(opts.cols[c])}</div>` +
          `<div>${escapeHtml(opts.tip(v))}</div>`;
      },
    },
    series: [
      {
        type: "heatmap",
        data,
        itemStyle: { borderColor: p.surface, borderWidth: 2, borderRadius: 3 },
        label: {
          show: true,
          fontSize: 11,
          formatter: (d: { data: [number, number, number, number] }) => opts.label(d.data[3]),
          color: p.ink,
        },
        emphasis: { itemStyle: { borderColor: p.ink, borderWidth: 1 } },
      },
    ],
  };
}

/** Multi-line time series (one axis). */
export function linesOption(opts: {
  series: { name: string; points: [string, number | null][]; colorIndex: number; emphasis?: boolean }[];
  yName: string;
  format: (v: number) => string;
  log?: boolean;
  xType?: "time" | "category";
}): EChartsCoreOption {
  const p = palette();
  return {
    animation: false,
    grid: { left: 8, right: 16, top: 28, bottom: 28, containLabel: true },
    xAxis: {
      type: opts.xType ?? "time",
      axisLine: { lineStyle: { color: p.axis } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: opts.xType === "category" ? baseText(p) : { ...baseText(p), formatter: "{yyyy}" },
      boundaryGap: opts.xType === "category" ? false : undefined,
    },
    yAxis: {
      type: opts.log ? "log" : "value",
      logBase: 10,
      name: opts.yName,
      nameTextStyle: { ...baseText(p), align: "left" },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: p.grid } },
      axisLabel: { ...baseText(p), formatter: (v: number) => opts.format(v) },
    },
    tooltip: {
      ...tooltipBox(p),
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: p.axis, width: 1 } },
      valueFormatter: (v: number) => (v == null ? "—" : opts.format(v)),
    },
    series: opts.series.map((s) => {
      // A point with no neighbour to draw a line to (between series breaks) gets a marker,
      // otherwise it would not be drawn at all.
      const isolated = s.points.map(([, v], i) =>
        v != null && (i === 0 || s.points[i - 1][1] == null) && (i === s.points.length - 1 || s.points[i + 1][1] == null));
      return {
        name: s.name,
        type: "line",
        showSymbol: isolated.some(Boolean),
        showAllSymbol: true,
        symbol: "circle",
        symbolSize: (_v: unknown, params: { dataIndex: number }) => (isolated[params.dataIndex] ? 8 : 0),
        connectNulls: false,
        lineStyle: { width: 2, color: p.series[s.colorIndex] },
        itemStyle: { color: p.series[s.colorIndex], borderColor: p.surface, borderWidth: 2 },
        data: s.points,
        emphasis: { focus: "series" },
      };
    }),
  };
}
