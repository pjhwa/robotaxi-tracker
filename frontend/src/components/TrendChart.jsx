import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

const PERIODS = [
  { label: "7일", value: 7 },
  { label: "30일", value: 30 },
  { label: "전체", value: null },
];

export default function TrendChart({ history, onPeriodChange, period }) {
  const data = history.map((h) => ({
    time: new Date(h.captured_at).toLocaleDateString("ko-KR"),
    count: h.vehicle_count,
  }));

  return (
    <div style={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, padding: 24, marginBottom: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2 style={{ color: "#fff", margin: 0, fontSize: 16 }}>Tesla 차량 수 변화</h2>
        <div style={{ display: "flex", gap: 8 }}>
          {PERIODS.map((p) => (
            <button
              key={p.label}
              onClick={() => onPeriodChange(p.value)}
              style={{
                background: period === p.value ? "#e82127" : "#333",
                color: "#fff",
                border: "none",
                borderRadius: 4,
                padding: "4px 12px",
                cursor: "pointer",
                fontSize: 12,
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis dataKey="time" stroke="#555" tick={{ fontSize: 11 }} />
          <YAxis stroke="#555" tick={{ fontSize: 11 }} />
          <Tooltip
            contentStyle={{ background: "#1a1a2e", border: "1px solid #555", color: "#fff" }}
          />
          <Line type="monotone" dataKey="count" stroke="#e82127" dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
