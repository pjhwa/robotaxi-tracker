import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LabelList, ResponsiveContainer, Cell,
} from "recharts";
import styles from "./ComparisonChart.module.css";

const TESLA_NAMES = ["tesla", "cybercab", "bot"];

function isTesla(name) {
  return TESLA_NAMES.some((k) => name?.toLowerCase().includes(k));
}

export default function ComparisonChart({ snapshots }) {
  const data = [...snapshots]
    .sort((a, b) => (b.vehicle_count ?? 0) - (a.vehicle_count ?? 0))
    .map((s) => ({ name: s.name, count: s.vehicle_count ?? 0 }));

  return (
    <div className={styles.card}>
      <div className={styles.title}>Operator Comparison</div>
      <ResponsiveContainer width="100%" height={Math.max(data.length * 48 + 20, 80)}>
        <BarChart data={data} layout="vertical" margin={{ left: 60, right: 40 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" horizontal={false} />
          <XAxis type="number" stroke="#2a2a2a" tick={{ fill: "#444", fontSize: 11, fontFamily: "Inter" }} />
          <YAxis type="category" dataKey="name" stroke="#2a2a2a" tick={{ fill: "#666", fontSize: 12, fontFamily: "Inter" }} width={56} />
          <Tooltip
            contentStyle={{ background: "#111", border: "1px solid #2a2a2a", borderRadius: 4, color: "#fff", fontFamily: "Inter", fontSize: 12 }}
            cursor={{ fill: "rgba(255,255,255,0.02)" }}
          />
          <Bar dataKey="count" radius={[0, 3, 3, 0]}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={isTesla(entry.name) ? "#e82127" : "#2a2a2a"} />
            ))}
            <LabelList dataKey="count" position="right" style={{ fill: "#555", fontSize: 11, fontFamily: "Inter" }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
