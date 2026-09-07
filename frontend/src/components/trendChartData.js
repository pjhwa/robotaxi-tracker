export function formatTickDate(date) {
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function compactDateTick(current, previous) {
  if (!previous) return current;
  const currentMonth = current.split(" ")[0];
  const prevMonth = previous.split(" ")[0];
  if (currentMonth === prevMonth) return current.split(" ")[1];
  return current;
}

export function spaceTicks(ticks, max) {
  if (ticks.length <= max) return ticks;
  if (max <= 1) return ticks.slice(0, max);
  const last = ticks.length - 1;
  const out = [];
  const used = new Set();
  for (let i = 0; i < max; i++) {
    const idx = Math.round((i * last) / (max - 1));
    if (used.has(idx)) continue;
    used.add(idx);
    out.push(ticks[idx]);
  }
  return out;
}

export function startOfLocalDay(ms) {
  const d = new Date(ms);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

export function calendarDays(startMs, endMs) {
  const days = [];
  const d = new Date(startOfLocalDay(startMs));
  const end = startOfLocalDay(endMs);
  while (d.getTime() <= end) {
    days.push(d.getTime());
    d.setDate(d.getDate() + 1);
  }
  return days;
}

export function toTrendChartModel(history, maxTicks = 40) {
  if (history.length === 0) return { data: [], ticks: [] };

  const points = history.map((h) => {
    const captured = new Date(h.captured_at);
    return {
      t: captured.getTime(),
      time: formatTickDate(captured),
      count: h.vehicle_count,
    };
  });

  const days = calendarDays(points[0].t, points[points.length - 1].t);
  const byDay = new Map();
  for (const point of points) {
    const day = startOfLocalDay(point.t);
    const list = byDay.get(day);
    if (list) list.push(point);
    else byDay.set(day, [point]);
  }

  let lastCount = points[0].count;
  const data = [];
  for (const day of days) {
    const dayPoints = byDay.get(day);
    if (dayPoints) {
      data.push(...dayPoints);
      lastCount = dayPoints[dayPoints.length - 1].count;
    } else {
      const noon = new Date(day);
      noon.setHours(12, 0, 0, 0);
      data.push({
        t: noon.getTime(),
        time: formatTickDate(new Date(day)),
        count: lastCount,
      });
    }
  }

  return { data, ticks: spaceTicks(days, maxTicks) };
}
