import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import styles from "./TrendChart.module.css";

const PERIODS = [
  { label: "7D", value: 7 },
  { label: "30D", value: 30 },
  { label: "All", value: null },
];

export default function TrendChart({ history, onPeriodChange, period }) {
  const data = history.map((h) => ({
    time: new Date(h.captured_at).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    count: h.vehicle_count,
  }));

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
      <ResponsiveContainer width="100%" height={220}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="redGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#e82127" stopOpacity={0.25} />
              <stop offset="95%" stopColor="#e82127" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" />
          <XAxis dataKey="time" stroke="#2a2a2a" tick={{ fill: "#444", fontSize: 11, fontFamily: "Plus Jakarta Sans" }} />
          <YAxis stroke="#2a2a2a" tick={{ fill: "#444", fontSize: 11, fontFamily: "Plus Jakarta Sans" }} />
          <Tooltip
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
            activeDot={{ r: 4, fill: "#e82127", strokeWidth: 0 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
