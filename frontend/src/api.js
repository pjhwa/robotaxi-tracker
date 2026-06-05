const BASE = "/api";

export async function fetchLatestSnapshots() {
  const r = await fetch(`${BASE}/snapshots/latest`);
  if (!r.ok) throw new Error("Failed to fetch snapshots");
  return r.json();
}

export async function fetchOperators() {
  const r = await fetch(`${BASE}/operators`);
  if (!r.ok) throw new Error("Failed to fetch operators");
  return r.json();
}

export async function fetchOperatorHistory(operatorId, days) {
  const params = days ? `?days=${days}` : "";
  const r = await fetch(`${BASE}/operators/${operatorId}/history${params}`);
  if (!r.ok) throw new Error("Failed to fetch history");
  return r.json();
}

export async function fetchChangeEvents(page = 1) {
  const r = await fetch(`${BASE}/events/changes?page=${page}`);
  if (!r.ok) throw new Error("Failed to fetch events");
  return r.json();
}
