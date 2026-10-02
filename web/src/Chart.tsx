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

/** Thin ECharts wrapper: SVG renderer, resizes with its container, replaces options on change. */
export function Chart({ option, height, ariaLabel }: { option: EChartsCoreOption; height: number; ariaLabel: string }) {
  const el = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!el.current) return;
    inst.current = echarts.init(el.current, undefined, { renderer: "svg" });
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

  return <div ref={el} className="chart" style={{ height }} role="img" aria-label={ariaLabel} />;
}
