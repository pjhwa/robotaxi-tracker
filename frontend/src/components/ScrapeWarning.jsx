function formatAge(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return null;
  if (seconds < 60) return `${seconds}초`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}분`;
  if (seconds < 86400) {
    const h = Math.floor(seconds / 3600);
    const m = Math.round((seconds % 3600) / 60);
    return m ? `${h}시간 ${m}분` : `${h}시간`;
  }
  const d = Math.floor(seconds / 86400);
  const h = Math.round((seconds % 86400) / 3600);
  return h ? `${d}일 ${h}시간` : `${d}일`;
}

function formatTime(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString("ko-KR", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/**
 * Build a human-readable warning from /health payload.
 * Returns null when status is ok (no banner needed).
 */
export function buildHealthWarning(health) {
  if (!health || health.status === "ok") return null;

  const age = formatAge(health.data_age_seconds);
  const lastOk = formatTime(health.last_success_at || health.last_scrape_at);
  const lastAttempt = formatTime(health.last_attempt_at);
  const ageSuffix = age ? ` (약 ${age} 전)` : "";
  const lastOkLine = lastOk
    ? `마지막 성공 수집: ${lastOk}${ageSuffix}`
    : "성공한 수집 기록이 없습니다.";

  switch (health.status) {
    case "failed":
      return {
        level: "error",
        title: "데이터 수집 실패",
        body: [
          "TxMCCS에서 차량 수치를 가져오지 못했습니다. 화면에 표시된 값은 최신이 아닐 수 있습니다.",
          lastOkLine,
          health.last_error ? `오류: ${health.last_error}` : null,
          lastAttempt ? `마지막 시도: ${lastAttempt}` : null,
        ].filter(Boolean),
      };
    case "stale":
      return {
        level: "warn",
        title: "데이터가 오래되었습니다",
        body: [
          "최근 스크랩이 반영되지 않아 수치가 부정확할 수 있습니다.",
          lastOkLine,
          health.last_error ? `최근 오류: ${health.last_error}` : null,
        ].filter(Boolean),
      };
    case "degraded":
      return {
        level: "warn",
        title: "일부 운영사 수집 실패",
        body: [
          `${health.operators_ok ?? "?"}개 성공 / ${health.operators_failed ?? "?"}개 실패.`,
          "일부 운영사 수치가 최신이 아닐 수 있습니다.",
          health.last_error || null,
        ].filter(Boolean),
      };
    case "no_data":
      return {
        level: "error",
        title: "데이터 없음",
        body: ["아직 수집된 스냅샷이 없습니다. 스크래퍼 상태를 확인하세요."],
      };
    default:
      return {
        level: "warn",
        title: "수집 상태 이상",
        body: [`상태: ${health.status}`, lastOkLine].filter(Boolean),
      };
  }
}

const styles = {
  error: {
    background: "rgba(232,33,39,0.1)",
    border: "1px solid rgba(232,33,39,0.45)",
    color: "#ff6b6f",
  },
  warn: {
    background: "rgba(245,158,11,0.1)",
    border: "1px solid rgba(245,158,11,0.45)",
    color: "#fbbf24",
  },
};

export default function ScrapeWarning({ health }) {
  const warning = buildHealthWarning(health);
  if (!warning) return null;

  const palette = styles[warning.level] || styles.warn;

  return (
    <div
      role="alert"
      style={{
        ...palette,
        borderRadius: 6,
        padding: "12px 16px",
        marginBottom: 20,
        fontSize: 13,
        lineHeight: 1.5,
      }}
    >
      <div style={{ fontWeight: 700, letterSpacing: "0.04em", marginBottom: 4 }}>
        ⚠ {warning.title}
      </div>
      {warning.body.map((line, i) => (
        <div key={i} style={{ opacity: 0.95 }}>
          {line}
        </div>
      ))}
    </div>
  );
}
