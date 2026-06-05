import { useState, useEffect, useCallback } from "react";
import Header from "./components/Header";
import SummaryCards from "./components/SummaryCards";
import TrendChart from "./components/TrendChart";
import ComparisonChart from "./components/ComparisonChart";
import ChangeLog from "./components/ChangeLog";
import {
  fetchLatestSnapshots,
  fetchOperatorHistory,
  fetchChangeEvents,
} from "./api";

const TESLA_PERMIT = "AV8313426653583";
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
  const [error, setError] = useState(null);

  const loadAll = useCallback(async () => {
    try {
      const [snaps, hist, evts] = await Promise.all([
        fetchLatestSnapshots(),
        fetchOperatorHistory(TESLA_PERMIT, period),
        fetchChangeEvents(eventsPage),
      ]);
      setSnapshots(snaps);
      setHistory(hist);
      setEvents(evts);
      setLastUpdated(new Date().toISOString());
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
      <Header lastUpdated={lastUpdated} />
      <main style={mainStyle}>
        {error && <div style={errorStyle}>{error}</div>}
        <SummaryCards snapshots={snapshots} />
        <TrendChart history={history} period={period} onPeriodChange={setPeriod} />
        <ComparisonChart snapshots={snapshots} />
        <ChangeLog events={events} page={eventsPage} onPageChange={(p) => setEventsPage(Math.max(1, p))} />
      </main>
    </div>
  );
}
