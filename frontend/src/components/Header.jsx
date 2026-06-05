export default function Header({ lastUpdated }) {
  const ago = lastUpdated
    ? Math.round((Date.now() - new Date(lastUpdated).getTime()) / 60000)
    : null;

  return (
    <header style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "16px 24px", borderBottom: "1px solid #222", marginBottom: 24,
    }}>
      <h1 style={{ color: "#fff", margin: 0, fontSize: 20 }}>
        🚖 Texas Robotaxi Tracker
      </h1>
      <span style={{ color: "#555", fontSize: 12 }}>
        {ago !== null ? `Last updated: ${ago}분 전` : "데이터 없음"}
      </span>
    </header>
  );
}
