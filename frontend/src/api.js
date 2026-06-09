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

export async function fetchVapidPublicKey() {
    const r = await fetch(`${BASE}/push/vapid-public-key`);
    if (!r.ok) throw new Error("Failed to fetch VAPID key");
    return r.json();
}

export async function subscribePush(subscription) {
    const r = await fetch(`${BASE}/push/subscribe`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            endpoint: subscription.endpoint,
            keys: subscription.keys,
        }),
    });
    if (!r.ok) throw new Error("Failed to save subscription");
    return r.json();
}

export async function unsubscribePush(endpoint) {
    const r = await fetch(`${BASE}/push/unsubscribe`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ endpoint }),
    });
    if (!r.ok) throw new Error("Failed to remove subscription");
    return r.json();
}
