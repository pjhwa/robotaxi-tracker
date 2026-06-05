export default function SummaryCards({ snapshots }) {
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 24 }}>
      {snapshots.map((s) => (
        <Card key={s.operator_id} snapshot={s} />
      ))}
    </div>
  );
}

function Card({ snapshot }) {
  const { name, vehicle_count, captured_at } = snapshot;
  return (
    <div style={{
      background: "#1a1a2e",
      border: "1px solid #333",
      borderRadius: 8,
      padding: "16px 24px",
      minWidth: 160,
    }}>
      <div style={{ color: "#888", fontSize: 12, marginBottom: 4 }}>{name}</div>
      <div style={{ color: "#fff", fontSize: 36, fontWeight: "bold", lineHeight: 1 }}>
        {vehicle_count ?? "—"}
      </div>
      <div style={{ color: "#555", fontSize: 11, marginTop: 4 }}>
        {captured_at ? new Date(captured_at).toLocaleString("ko-KR") : ""}
      </div>
    </div>
  );
}
