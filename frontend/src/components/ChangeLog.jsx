import styles from "./ChangeLog.module.css";

export default function ChangeLog({ events, onPageChange, page }) {
  return (
    <div className={styles.card}>
      <div className={styles.title}>Change Events</div>
      {events.length === 0 ? (
        <p className={styles.empty}>No change events yet.</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Time</th>
              <th>Operator</th>
              <th>Change</th>
              <th>Delta</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e, i) => (
              <tr key={i}>
                <td>{new Date(e.captured_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</td>
                <td style={{ color: "#888" }}>{e.operator_name}</td>
                <td>{e.old_count} → {e.new_count}</td>
                <td>
                  <span className={`${styles.badge} ${e.delta > 0 ? styles.badgeUp : styles.badgeDown}`}>
                    {e.delta > 0 ? `+${e.delta}` : e.delta}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className={styles.pagination}>
        <button
          className={styles.pageBtn}
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
        >
          ←
        </button>
        <span className={styles.pageNum}>{page}</span>
        <button
          className={styles.pageBtn}
          onClick={() => onPageChange(page + 1)}
          disabled={events.length < 20}
        >
          →
        </button>
      </div>
    </div>
  );
}
