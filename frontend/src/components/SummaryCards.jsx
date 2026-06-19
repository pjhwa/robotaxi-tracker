import styles from "./SummaryCards.module.css";

export default function SummaryCards({ snapshots, teslaId }) {
  const sorted = [...snapshots].sort((a, b) => (b.vehicle_count ?? 0) - (a.vehicle_count ?? 0));
  const tesla = sorted.find((s) => s.operator_id === teslaId);
  const teslaRank = tesla ? sorted.findIndex((s) => s.operator_id === teslaId) + 1 : null;
  const others = sorted.filter((s) => s.operator_id !== teslaId);

  return (
    <div className={styles.wrapper}>
      {tesla && (
        <div className={styles.teslaCard}>
          <div className={styles.teslaLeft}>
            <div className={styles.teslaName}>Tesla Robotaxi</div>
            <div className={styles.teslaCount}>{tesla.vehicle_count ?? "—"}</div>
            <div className={styles.teslaLabel}>Vehicles Permitted · Texas</div>
            {tesla.vehicle_composition && tesla.vehicle_composition.length > 0 && (
              <div className={styles.compositionList}>
                {tesla.vehicle_composition.map((item, i) => (
                  <div key={i} className={styles.compositionRow}>
                    <span className={styles.compositionModel}>{item.model}</span>
                    <span className={styles.compositionYear}>{item.year ?? "—"}</span>
                    <span className={styles.compositionCount}>{item.count}대</span>
                  </div>
                ))}
              </div>
            )}
          </div>
          {teslaRank && (
            <div className={styles.teslaRight}>
              #{teslaRank} in Texas
            </div>
          )}
        </div>
      )}

      {others.length > 0 && (
        <>
          <div className={styles.othersLabel}>Other Operators</div>
          <div className={styles.othersGrid}>
            {others.map((s) => (
              <div key={s.operator_id} className={styles.otherCard}>
                <div className={styles.otherName}>{s.name}</div>
                <div className={styles.otherCount}>{s.vehicle_count ?? "—"}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
