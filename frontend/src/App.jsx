import { useState, useEffect, useCallback } from "react";
import Header from "./components/Header";
import SummaryCards from "./components/SummaryCards";
import TrendChart from "./components/TrendChart";
import ComparisonChart from "./components/ComparisonChart";
import ChangeLog from "./components/ChangeLog";
import ScrapeWarning from "./components/ScrapeWarning";
import {
  fetchLatestSnapshots,
  fetchOperatorHistory,
  fetchChangeEvents,
  fetchHealth,
} from "./api";

const TESLA_PERMIT = "AV8313426653583";

function OtherOperators({ snapshots, teslaId }) {
  const others = [...snapshots]
    .filter((s) => s.operator_id !== teslaId)
    .sort((a, b) => (b.vehicle_count ?? 0) - (a.vehicle_count ?? 0));
  if (others.length === 0) return null;
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.15em", textTransform: "uppercase", color: "#444", marginBottom: 10 }}>
        Other Operators
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {others.map((s) => (
          <div key={s.operator_id} style={{ flex: 1, minWidth: 140, background: "#080808", border: "1px solid #161616", borderRadius: 4, padding: "12px 16px" }}>
            <div style={{ fontSize: 10, fontWeight: 500, color: "#555", marginBottom: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {s.name.replace(/ (LLC|INC|INCORPORATED|CO LLC)\.?$/i, "")}
            </div>
            <div style={{ fontSize: 22, fontWeight: 600, color: "#555", lineHeight: 1, letterSpacing: "-0.01em" }}>
              {s.vehicle_count ?? "—"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
const REFRESH_MS = 15 * 60 * 1000;

const errorStyle = {
  background: "rgba(232,33,39,0.08)",
  border: "1px solid rgba(232,33,39,0.3)",
  borderRadius: 6,
  padding: "10px 16px",
  marginBottom: 20,
  color: "#e82127",
  fontSize: 13,
};

const mainStyle = {
  maxWidth: 1100,
  margin: "0 auto",
  padding: "32px 24px 64px",
};

export default function App() {
  const [snapshots, setSnapshots] = useState([]);
  const [history, setHistory] = useState([]);
  const [events, setEvents] = useState([]);
  const [period, setPeriod] = useState(30);
  const [eventsPage, setEventsPage] = useState(1);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [snaps, hist, evts, h] = await Promise.all([
        fetchLatestSnapshots(),
        fetchOperatorHistory(TESLA_PERMIT, period),
        fetchChangeEvents(eventsPage),
        fetchHealth(),
      ]);
      setSnapshots(snaps);
      setHistory(hist);
      setEvents(evts);
      setHealth(h);
      setLastUpdated(h?.last_success_at || h?.last_scrape_at || new Date().toISOString());
      setError(null);
    } catch (e) {
      setError("Failed to load data: " + e.message);
    }
  }, [period, eventsPage]);

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, REFRESH_MS);
    return () => clearInterval(id);
  }, [loadAll]);

  return (
    <div style={{ background: "#000", minHeight: "100vh" }}>
      <Header lastUpdated={lastUpdated} health={health} />
      <main style={mainStyle}>
        {error && <div style={errorStyle}>{error}</div>}
        <ScrapeWarning health={health} />
        <SummaryCards snapshots={snapshots} teslaId={TESLA_PERMIT} />
        <TrendChart history={history} period={period} onPeriodChange={setPeriod} />
        <ComparisonChart snapshots={snapshots} teslaId={TESLA_PERMIT} />
        <OtherOperators snapshots={snapshots} teslaId={TESLA_PERMIT} />
        <ChangeLog events={events} page={eventsPage} onPageChange={(p) => setEventsPage(Math.max(1, p))} />
      </main>
    </div>
  );
}
