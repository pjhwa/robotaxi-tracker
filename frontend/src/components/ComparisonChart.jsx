import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  LabelList, ResponsiveContainer,
} from "recharts";

export default function ComparisonChart({ snapshots }) {
  const data = [...snapshots]
    .sort((a, b) => (b.vehicle_count ?? 0) - (a.vehicle_count ?? 0))
    .map((s) => ({ name: s.name, count: s.vehicle_count ?? 0 }));

  return (
    <div style={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, padding: 24, marginBottom: 24 }}>
      <h2 style={{ color: "#fff", margin: "0 0 16px", fontSize: 16 }}>운영사 비교 (현재)</h2>
      <ResponsiveContainer width="100%" height={Math.max(data.length * 44 + 20, 80)}>
        <BarChart data={data} layout="vertical" margin={{ left: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={false} />
          <XAxis type="number" stroke="#555" tick={{ fontSize: 11 }} />
          <YAxis type="category" dataKey="name" stroke="#555" tick={{ fontSize: 12 }} width={56} />
          <Tooltip
            contentStyle={{ background: "#1a1a2e", border: "1px solid #555", color: "#fff" }}
          />
          <Bar dataKey="count" fill="#00d4aa" radius={[0, 4, 4, 0]}>
            <LabelList dataKey="count" position="right" style={{ fill: "#aaa", fontSize: 12 }} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
