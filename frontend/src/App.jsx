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
      setError("데이터 로딩 실패: " + e.message);
    }
  }, [period, eventsPage]);

  useEffect(() => {
    loadAll();
    const id = setInterval(loadAll, REFRESH_MS);
    return () => clearInterval(id);
  }, [loadAll]);

  const handlePeriodChange = (p) => { setPeriod(p); };
  const handlePageChange = (p) => { setEventsPage(Math.max(1, p)); };

  return (
    <div style={{ background: "#0d0d1a", minHeight: "100vh", color: "#fff", fontFamily: "system-ui, sans-serif" }}>
      <Header lastUpdated={lastUpdated} />
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "0 24px 48px" }}>
        {error && (
          <div style={{ background: "#3a1a1a", border: "1px solid #e82127", borderRadius: 6, padding: "10px 16px", marginBottom: 16, color: "#e82127" }}>
            {error}
          </div>
        )}
        <SummaryCards snapshots={snapshots} />
        <TrendChart history={history} period={period} onPeriodChange={handlePeriodChange} />
        <ComparisonChart snapshots={snapshots} />
        <ChangeLog events={events} page={eventsPage} onPageChange={handlePageChange} />
      </main>
    </div>
  );
}
