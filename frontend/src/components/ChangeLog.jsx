export default function ChangeLog({ events, onPageChange, page }) {
  return (
    <div style={{ background: "#1a1a2e", border: "1px solid #333", borderRadius: 8, padding: 24, marginBottom: 24 }}>
      <h2 style={{ color: "#fff", margin: "0 0 16px", fontSize: 16 }}>변경 이벤트 로그</h2>
      {events.length === 0 ? (
        <p style={{ color: "#555" }}>아직 변경 이벤트가 없습니다.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead>
            <tr style={{ color: "#666", borderBottom: "1px solid #333" }}>
              <th style={{ textAlign: "left", padding: "4px 8px" }}>시간</th>
              <th style={{ textAlign: "left", padding: "4px 8px" }}>운영사</th>
              <th style={{ textAlign: "right", padding: "4px 8px" }}>변화</th>
              <th style={{ textAlign: "right", padding: "4px 8px" }}>증감</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #222", color: "#ccc" }}>
                <td style={{ padding: "6px 8px" }}>
                  {new Date(e.captured_at).toLocaleString("ko-KR")}
                </td>
                <td style={{ padding: "6px 8px" }}>{e.operator_name}</td>
                <td style={{ padding: "6px 8px", textAlign: "right" }}>
                  {e.old_count} → {e.new_count}
                </td>
                <td style={{
                  padding: "6px 8px", textAlign: "right",
                  color: e.delta > 0 ? "#00d4aa" : "#e82127",
                }}>
                  {e.delta > 0 ? `+${e.delta}` : e.delta}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "flex-end" }}>
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          style={{ background: "#333", color: "#fff", border: "none", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}
        >
          ←
        </button>
        <span style={{ color: "#666", fontSize: 12, lineHeight: "26px" }}>p.{page}</span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={events.length < 20}
          style={{ background: "#333", color: "#fff", border: "none", borderRadius: 4, padding: "4px 10px", cursor: "pointer" }}
        >
          →
        </button>
      </div>
    </div>
  );
}
