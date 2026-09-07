import { Component, useEffect, useState } from "react";
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { compactDateTick, formatTickDate, toTrendChartModel } from "./trendChartData";
import styles from "./TrendChart.module.css";

const PERIODS = [
  { label: "7D", value: 7 },
  { label: "30D", value: 30 },
  { label: "All", value: null },
];

class ChartErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className={styles.card}>
          <span className={styles.title}>Tesla Fleet Size</span>
        </div>
      );
    }
    return this.props.children;
  }
}

function useMaxDateTicks() {
  const [maxTicks, setMaxTicks] = useState(40);
  useEffect(() => {
    const update = () => setMaxTicks(window.innerWidth < 640 ? 8 : 40);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);
  return maxTicks;
}

function TrendChartInner({ history, onPeriodChange, period }) {
  const maxTicks = useMaxDateTicks();
  const { data, ticks } = toTrendChartModel(history, maxTicks);
  const domain = data.length ? [data[0].t, data[data.length - 1].t] : [0, 1];

  return (
    <div className={styles.card}>
      <div className={styles.header}>
        <span className={styles.title}>Tesla Fleet Size</span>
        <div className={styles.pills}>
          {PERIODS.map((p) => (
            <button
              key={p.label}
              onClick={() => onPeriodChange(p.value)}
              className={`${styles.pill} ${period === p.value ? styles.pillActive : ""}`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      {data.length > 0 && (
        <div className={styles.chartWrap}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data}>
              <defs>
                <linearGradient id="redGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#e82127" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#e82127" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
              <XAxis
                type="number"
                dataKey="t"
                domain={domain}
                ticks={ticks}
                interval={0}
                tickFormatter={(value, index) => {
                  const label = formatTickDate(new Date(value));
                  const prev = index > 0 ? formatTickDate(new Date(ticks[index - 1])) : null;
                  return compactDateTick(label, prev);
                }}
                stroke="#2a2a2a"
                tick={{ fill: "#444", fontSize: 11, fontFamily: "Plus Jakarta Sans" }}
              />
              <YAxis stroke="#2a2a2a" tick={{ fill: "#444", fontSize: 11, fontFamily: "Plus Jakarta Sans" }} />
              <Tooltip
                labelFormatter={(t) => new Date(t).toLocaleString("en-US", {
                  month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
                })}
                contentStyle={{ background: "#111", border: "1px solid #2a2a2a", borderRadius: 4, color: "#fff", fontFamily: "Plus Jakarta Sans", fontSize: 12 }}
                cursor={{ stroke: "#333" }}
              />
              <Area
                type="monotone"
                dataKey="count"
                stroke="#e82127"
                strokeWidth={2}
                fill="url(#redGrad)"
                dot={false}
                isAnimationActive={false}
                activeDot={{ r: 4, fill: "#e82127", strokeWidth: 0 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

export default function TrendChart(props) {
  return (
    <ChartErrorBoundary>
      <TrendChartInner {...props} />
    </ChartErrorBoundary>
  );
}
