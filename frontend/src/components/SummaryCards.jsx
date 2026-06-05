import styles from "./SummaryCards.module.css";

export default function SummaryCards({ snapshots }) {
  return (
    <div className={styles.grid}>
      {snapshots.map((s) => (
        <Card key={s.operator_id} snapshot={s} />
      ))}
    </div>
  );
}

function Card({ snapshot }) {
  const { name, vehicle_count } = snapshot;
  return (
    <div className={styles.card}>
      <div className={styles.name}>{name}</div>
      <div className={styles.count}>{vehicle_count ?? "—"}</div>
      <div className={styles.label}>Vehicles Permitted</div>
    </div>
  );
}
