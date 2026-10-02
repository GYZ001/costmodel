import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { BarChart, CustomChart, HeatmapChart, LineChart, ScatterChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";

echarts.use([
  BarChart, LineChart, ScatterChart, HeatmapChart, CustomChart,
  GridComponent, TooltipComponent, MarkLineComponent, VisualMapComponent, DataZoomComponent,
  SVGRenderer,
]);

/** Thin ECharts wrapper: SVG renderer, resizes with its container, replaces options on change.
 *  onPick receives the category name of a clicked bar, point or axis label. */
export function Chart({ option, height, ariaLabel, onPick }: {
  option: EChartsCoreOption; height: number; ariaLabel: string; onPick?: (name: string) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);
  const pick = useRef(onPick);
  pick.current = onPick;

  useEffect(() => {
    if (!el.current) return;
    inst.current = echarts.init(el.current, undefined, { renderer: "svg" });
    inst.current.on("click", (p: { componentType?: string; name?: string; value?: unknown }) => {
      const name = p.componentType === "yAxis" || p.componentType === "xAxis" ? String(p.value ?? "") : p.name;
      if (name && pick.current) pick.current(name);
    });
    const ro = new ResizeObserver(() => inst.current?.resize());
    ro.observe(el.current);
    return () => {
      ro.disconnect();
      inst.current?.dispose();
      inst.current = null;
    };
  }, []);

  useEffect(() => {
    inst.current?.setOption(option, { notMerge: true });
  }, [option]);

  useEffect(() => {
    inst.current?.resize();
  }, [height]);

  return <div ref={el} className={`chart${onPick ? " pickable" : ""}`} style={{ height }} role="img" aria-label={ariaLabel} dir="ltr" />;
}
