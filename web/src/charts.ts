import type { EChartsCoreOption } from "echarts/core";
import { cssVar, escapeHtml, palette } from "./lib";

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
// The page's font stack for the current language (styles.css --font).
const font = () => cssVar("--font") || "sans-serif";

function baseText(p: ReturnType<typeof palette>) {
  return { color: p.ink2, fontSize: AXIS_FONT, fontFamily: font() };
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
        b: { color: p.ink, fontWeight: 600, fontSize: AXIS_FONT, fontFamily: font() },
        n: { color: p.ink2, fontSize: AXIS_FONT, fontFamily: font() },
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
    extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,.12); border-radius: 8px; max-width: 400px; white-space: normal;",
    confine: true, // kept inside the chart, never off-screen
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

/** Horizontal ranking of a ratio with a reference line (e.g. 100% = one month's wage),
 *  hollow dots for the same ratio computed with other figures of the same row, and an
 *  optional aligned side panel (its own axis, 0–100%) for a context share. Largest at top. */
export function ratioRankingOption(opts: {
  items: (RankItem & { others: { value: number; label: string }[]; side: number | null })[];
  valueName: string;
  otherName: string;
  sideName?: string; // omit to leave the side panel out (narrow screens)
  sideWidth?: number; // px available for the side panel's title
  splitNumber?: number; // fewer value-axis ticks on narrow screens
  ref: { value: number; label: string };
  format: (v: number) => string;
  sideFormat: (v: number) => string;
  kv: KV;
}): EChartsCoreOption {
  const p = palette();
  const items = [...opts.items].sort((a, b) => a.value - b.value);
  const names = items.map((i) => i.name);
  const byName = new Map(items.map((i) => [i.name, i]));
  const anyFocus = items.some((i) => i.highlight);
  const labelled = (i: RankItem | undefined) => !!i && (i.highlight || (!anyFocus && items.length <= 25));
  const left = labelWidth(names);
  const side = !!opts.sideName;
  const mainRight = side ? "27%" : 72;
  const yBase = categoryAxis(p, names, (n) => !!byName.get(n)?.highlight);
  return {
    animation: false,
    grid: [
      { left, right: mainRight, top: 24, bottom: 28, containLabel: false },
      ...(side ? [{ left: "77%", right: 16, top: 24, bottom: 28, containLabel: false }] : []),
    ],
    xAxis: [
      {
        type: "value", min: 0, gridIndex: 0, splitNumber: opts.splitNumber,
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: p.grid, width: 1 } },
        axisLabel: { ...baseText(p), hideOverlap: true, formatter: (v: number) => opts.format(v) },
      },
      ...(side ? [{
        type: "value", min: 0, max: 1, gridIndex: 1, splitNumber: 2,
        axisLine: { show: false }, axisTick: { show: false },
        splitLine: { lineStyle: { color: p.grid, width: 1 } },
        axisLabel: { ...baseText(p), fontSize: 10.5, hideOverlap: true, formatter: (v: number) => opts.sideFormat(v) },
      }] : []),
    ],
    // The side panel's title sits in the top margin, where the main panel has the reference label.
    graphic: side ? [{ type: "text", left: "77%", top: 4, silent: true,
      style: { text: opts.sideName, fill: p.ink2, fontSize: 11, fontFamily: font(), width: opts.sideWidth, overflow: "truncate" } }] : [],
    yAxis: [
      { ...yBase, gridIndex: 0 },
      ...(side ? [{ ...yBase, gridIndex: 1, axisLabel: { show: false }, axisLine: { lineStyle: { color: p.axis } } }] : []),
    ],
    tooltip: {
      ...tooltipBox(p),
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: p.grid, opacity: 0.35 } },
      formatter: (params: { name: string }[]) => {
        const it = byName.get(params[0]?.name);
        if (!it) return "";
        const others = it.others.map((o) => `<div>${escapeHtml(opts.kv(o.label, opts.format(o.value)))}</div>`).join("");
        return `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(it.name)}</div>` +
          `<div><b>${escapeHtml(opts.kv(opts.valueName, opts.format(it.value)))}</b></div>${others}` +
          it.tip.map((t) => `<div style="color:${p.ink2}">${escapeHtml(t)}</div>`).join("");
      },
    },
    series: [
      {
        name: opts.valueName,
        type: "bar",
        xAxisIndex: 0, yAxisIndex: 0,
        barMaxWidth: 14,
        barCategoryGap: "30%",
        data: items.map((i) => ({
          value: i.value,
          itemStyle: { color: i.highlight || !anyFocus ? p.accent : p.deemph, borderRadius: [0, 4, 4, 0] },
        })),
        markLine: {
          silent: true, symbol: "none",
          lineStyle: { color: p.ink2, type: "dashed", width: 1 },
          label: { formatter: opts.ref.label, position: "end", color: p.ink2, fontSize: 11 },
          data: [{ xAxis: opts.ref.value }],
        },
        z: 2,
      },
      {
        name: opts.otherName,
        type: "scatter",
        xAxisIndex: 0, yAxisIndex: 0,
        symbolSize: 8,
        itemStyle: { color: p.surface, borderColor: p.ink2, borderWidth: 1.5 },
        data: items.flatMap((i) => i.others.map((o) => [o.value, i.name])),
        z: 3,
      },
      {
        // The bars' values, on a layer above the dots, on the page colour: a dot never covers a number.
        type: "scatter",
        xAxisIndex: 0, yAxisIndex: 0,
        symbol: "circle", symbolSize: 1, itemStyle: { color: "transparent" }, silent: true, tooltip: { show: false },
        data: items.filter((i) => labelled(i)).map((i) => [i.value, i.name]),
        label: {
          show: true, position: "right", distance: 4, color: p.ink2, fontSize: 11.5,
          backgroundColor: p.surface, padding: [1, 2], borderRadius: 2,
          formatter: (d: { value: [number, string] }) => opts.format(d.value[0]),
        },
        z: 4,
      },
      ...(side ? [{
        name: opts.sideName,
        type: "bar",
        xAxisIndex: 1, yAxisIndex: 1,
        barMaxWidth: 10,
        barCategoryGap: "30%",
        itemStyle: { color: p.deemph, borderRadius: [0, 3, 3, 0] },
        data: items.map((i) => i.side),
        label: {
          show: true, position: "right", color: p.ink2, fontSize: 10.5,
          formatter: (d: { value: number | null }) => (d.value != null ? opts.sideFormat(d.value) : ""),
        },
      }] : []),
    ],
  };
}

/** Horizontal stacked bars of a composition (fixed part order; the last part neutral grey),
 *  with a signed extra: a hatched segment where it is positive, a tick at the row's total
 *  where it is negative (the parts then add up to more than the total). Optional reference line. */
export function compositionOption(opts: {
  rows: { name: string; parts: number[]; partNotes?: (string | null)[]; total: number; extra: number; highlight: boolean; tip: string[] }[];
  partNames: string[];
  extraName: string;
  totalName: string;
  order: (a: { parts: number[]; total: number }, b: { parts: number[]; total: number }) => number; // top first
  format: (v: number) => string;
  ref?: { value: number; label: string };
  endLabel?: (r: { parts: number[]; total: number }) => string; // default: the total
  splitNumber?: number; // fewer value-axis ticks on narrow screens
  kv: KV;
}): EChartsCoreOption {
  const p = palette();
  const rows = [...opts.rows].sort(opts.order);
  const names = rows.map((r) => r.name);
  const byName = new Map(rows.map((r) => [r.name, r]));
  const last = opts.partNames.length - 1;
  const colorOf = (k: number) => (k === last ? p.deemph : p.series[k]);
  const inverse = true; // rows top first, so a vertical line runs from the top: its label goes at its start
  return {
    animation: false,
    grid: { left: labelWidth(names), right: 64, top: opts.ref ? 24 : 8, bottom: 28, containLabel: false },
    xAxis: {
      type: "value", min: 0, splitNumber: opts.splitNumber,
      axisLine: { show: false }, axisTick: { show: false },
      splitLine: { lineStyle: { color: p.grid } },
      axisLabel: { ...baseText(p), hideOverlap: true, formatter: (v: number) => opts.format(v) },
    },
    yAxis: categoryAxis(p, names, (n) => !!byName.get(n)?.highlight, inverse),
    tooltip: {
      ...tooltipBox(p),
      trigger: "axis",
      axisPointer: { type: "shadow", shadowStyle: { color: p.grid, opacity: 0.35 } },
      formatter: (params: { name: string }[]) => {
        const r = byName.get(params[0]?.name);
        if (!r) return "";
        const sw = (c: string) => `<span style="display:inline-block;width:14px;height:2px;background:${c};vertical-align:4px;margin-inline-end:6px"></span>`;
        const lines = opts.partNames.map((pn, k) => {
          const note = r.partNotes?.[k];
          return `<div>${sw(colorOf(k))}${escapeHtml(opts.kv(pn, opts.format(r.parts[k]) + (note ? ` · ${note}` : "")))}</div>`;
        }).join("");
        const extra = r.extra !== 0 ? `<div>${sw(p.axis)}${escapeHtml(opts.kv(opts.extraName, (r.extra < 0 ? "−" : "") + opts.format(Math.abs(r.extra))))}</div>` : "";
        return `<div style="font-weight:600;margin-bottom:2px">${escapeHtml(r.name)}</div><div><b>${escapeHtml(opts.kv(opts.totalName, opts.format(r.total)))}</b></div>${lines}${extra}` +
          r.tip.map((t) => `<div style="color:${p.ink2}">${escapeHtml(t)}</div>`).join("");
      },
    },
    series: [
      ...opts.partNames.map((pn, k) => ({
        name: pn,
        type: "bar",
        stack: "total",
        barMaxWidth: 14,
        barCategoryGap: "30%",
        itemStyle: { color: colorOf(k), borderColor: p.surface, borderWidth: 1 },
        data: rows.map((r) => r.parts[k]),
        ...(k === 0 && opts.ref ? {
          markLine: {
            silent: true, symbol: "none",
            lineStyle: { color: p.ink2, type: "dashed", width: 1 },
            label: { formatter: opts.ref.label, position: inverse ? "start" : "end", color: p.ink2, fontSize: 11 },
            data: [{ xAxis: opts.ref.value }],
          },
        } : {}),
      })),
      {
        name: opts.extraName,
        type: "bar",
        stack: "total",
        barMaxWidth: 14,
        barCategoryGap: "30%",
        itemStyle: {
          color: p.surface, borderColor: p.axis, borderWidth: 1,
          decal: { symbol: "rect", dashArrayX: [1, 0], dashArrayY: [2, 3], rotation: Math.PI / 4, color: p.axis },
        },
        data: rows.map((r) => (r.extra > 0 ? r.extra : 0)),
        label: {
          show: true, position: "right", color: p.ink2, fontSize: 11.5,
          formatter: (d: { name: string }) => { const r = byName.get(d.name); return r ? (opts.endLabel ? opts.endLabel(r) : opts.format(r.total)) : ""; },
        },
      },
      {
        name: opts.totalName,
        type: "scatter",
        symbol: "rect",
        symbolSize: [2, 14],
        itemStyle: { color: p.ink },
        data: rows.map((r) => (r.extra < 0 ? [r.total, r.name] : null)).filter(Boolean),
        z: 4,
      },
    ],
  };
}
