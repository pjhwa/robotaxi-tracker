import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LabelList, ResponsiveContainer, Cell,
} from "recharts";
import styles from "./ComparisonChart.module.css";

export default function ComparisonChart({ snapshots, teslaId }) {
  const data = [...snapshots]
    .sort((a, b) => (b.vehicle_count ?? 0) - (a.vehicle_count ?? 0))
    .map((s) => ({
      name: s.name,
      count: s.vehicle_count ?? 0,
      isTesla: s.operator_id === teslaId,
    }));

  return (
    <div className={styles.card}>
      <div className={styles.title}>Operator Comparison</div>
      <ResponsiveContainer width="100%" height={Math.max(data.length * 48 + 20, 80)}>
        <BarChart data={data} layout="vertical" margin={{ left: 60, right: 48 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1a1a1a" horizontal={false} />
          <XAxis type="number" stroke="#2a2a2a" tick={{ fill: "#333", fontSize: 11, fontFamily: "Plus Jakarta Sans" }} />
          <YAxis
            type="category"
            dataKey="name"
            stroke="#2a2a2a"
            tick={({ x, y, payload }) => {
              const item = data.find((d) => d.name === payload.value);
              return (
                <text x={x} y={y} dy={4} textAnchor="end" fontSize={11} fontFamily="Plus Jakarta Sans"
                  fill={item?.isTesla ? "#e82127" : "#333"}>
                  {payload.value.replace(/ (LLC|INC|INCORPORATED|CO LLC)\.?$/i, "")}
                </text>
              );
            }}
            width={56}
          />
          <Tooltip
            contentStyle={{ background: "#111", border: "1px solid #2a2a2a", borderRadius: 4, color: "#fff", fontFamily: "Plus Jakarta Sans", fontSize: 12 }}
            cursor={{ fill: "rgba(255,255,255,0.02)" }}
          />
          <Bar dataKey="count" radius={[0, 3, 3, 0]}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.isTesla ? "#e82127" : "#1e1e1e"} />
            ))}
            <LabelList
              dataKey="count"
              position="right"
              formatter={(v, _, props) => v}
              style={{ fill: "#444", fontSize: 11, fontFamily: "Plus Jakarta Sans" }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
