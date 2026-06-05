import styles from "./Header.module.css";

export default function Header({ lastUpdated }) {
  const ago = lastUpdated
    ? Math.round((Date.now() - new Date(lastUpdated).getTime()) / 60000)
    : null;

  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <span className={styles.title}>Texas Robotaxi Tracker</span>
        <span className={styles.subtitle}>Powered by TxMCCS</span>
      </div>
      <div className={styles.status}>
        <span className={styles.liveDot} />
        <span className={styles.liveLabel}>Live</span>
        <span className={styles.updatedAt}>
          {ago !== null ? `Updated ${ago}m ago` : "No data"}
        </span>
      </div>
    </header>
  );
}
