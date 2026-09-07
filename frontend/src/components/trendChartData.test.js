import { test } from "node:test";
import assert from "node:assert/strict";
import { compactDateTick, formatTickDate, parseCapturedAt, spaceTicks, toTrendChartModel } from "./trendChartData.js";

test("keeps every snapshot as a chart point", () => {
  const history = [
    { captured_at: "2026-08-08T12:00:00Z", vehicle_count: 10 },
    { captured_at: "2026-08-08T18:00:00Z", vehicle_count: 11 },
    { captured_at: "2026-08-09T12:00:00Z", vehicle_count: 12 },
  ];

  const { data } = toTrendChartModel(history);

  assert.equal(data.length, 3);
  assert.deepEqual(data.map((d) => d.count), [10, 11, 12]);
});

test("x-axis ticks include each calendar date only once", () => {
  const history = [
    { captured_at: new Date(2026, 7, 8, 12).toISOString(), vehicle_count: 10 },
    { captured_at: new Date(2026, 7, 8, 13).toISOString(), vehicle_count: 10 },
    { captured_at: new Date(2026, 7, 9, 12).toISOString(), vehicle_count: 11 },
    { captured_at: new Date(2026, 7, 9, 13).toISOString(), vehicle_count: 11 },
    { captured_at: new Date(2026, 7, 9, 14).toISOString(), vehicle_count: 12 },
    { captured_at: new Date(2026, 7, 10, 12).toISOString(), vehicle_count: 12 },
    { captured_at: new Date(2026, 7, 10, 13).toISOString(), vehicle_count: 13 },
  ];

  const { data, ticks } = toTrendChartModel(history);
  const labels = ticks.map((t) => formatTickDate(new Date(t)));

  assert.equal(new Set(labels).size, labels.length);
  assert.deepEqual(labels, ["Aug 8", "Aug 9", "Aug 10"]);
  assert.ok(data.length >= 7);
});

test("fills missing calendar days with the last known count", () => {
  const history = [
    { captured_at: new Date(2026, 7, 8, 12).toISOString(), vehicle_count: 10 },
    { captured_at: new Date(2026, 7, 9, 12).toISOString(), vehicle_count: 11 },
    { captured_at: new Date(2026, 7, 11, 12).toISOString(), vehicle_count: 12 },
  ];

  const { data, ticks } = toTrendChartModel(history);
  const labels = ticks.map((t) => formatTickDate(new Date(t)));

  assert.deepEqual(labels, ["Aug 8", "Aug 9", "Aug 10", "Aug 11"]);
  const filled = data.find((d) => d.time === "Aug 10");
  assert.ok(filled);
  assert.equal(filled.count, 11);
});

test("returns empty data and ticks for empty history", () => {
  const { data, ticks } = toTrendChartModel([]);
  assert.deepEqual(data, []);
  assert.deepEqual(ticks, []);
});

test("parseCapturedAt accepts Python isoformat with microseconds", () => {
  const d = parseCapturedAt("2026-09-07T22:46:18.448719+00:00");
  assert.ok(d instanceof Date);
  assert.ok(Number.isFinite(d.getTime()));
});

test("toTrendChartModel never emits non-finite x values", () => {
  const { data, ticks } = toTrendChartModel([
    { captured_at: "not-a-date", vehicle_count: 1 },
    { captured_at: "2026-08-08T12:00:00.574956+00:00", vehicle_count: 10 },
    { captured_at: "2026-08-09T12:00:00.123456+00:00", vehicle_count: 11 },
  ]);
  assert.ok(data.length >= 2);
  assert.ok(data.every((d) => Number.isFinite(d.t)));
  assert.ok(ticks.every((t) => Number.isFinite(t)));
});

test("compactDateTick keeps the month on the first tick and when the month changes", () => {
  assert.equal(compactDateTick("Aug 8", null), "Aug 8");
  assert.equal(compactDateTick("Aug 9", "Aug 8"), "9");
  assert.equal(compactDateTick("Aug 10", "Aug 9"), "10");
  assert.equal(compactDateTick("Sep 1", "Aug 31"), "Sep 1");
  assert.equal(compactDateTick("Sep 2", "Sep 1"), "2");
});

test("spaceTicks keeps every date when they already fit", () => {
  const ticks = ["Aug 8", "Aug 9", "Aug 10", "Aug 11"];
  assert.deepEqual(spaceTicks(ticks, 8), ticks);
});

test("spaceTicks fills the range evenly and keeps both ends when thinning", () => {
  const ticks = Array.from({ length: 10 }, (_, i) => `D${i}`);
  const spaced = spaceTicks(ticks, 4);
  assert.deepEqual(spaced, ["D0", "D3", "D6", "D9"]);
  assert.equal(spaced[0], ticks[0]);
  assert.equal(spaced.at(-1), ticks.at(-1));
});

test("toTrendChartModel thins calendar ticks to maxTicks and keeps both ends", () => {
  const history = Array.from({ length: 20 }, (_, i) => ({
    captured_at: new Date(2026, 5, i + 1, 12).toISOString(),
    vehicle_count: i + 1,
  }));
  const { ticks } = toTrendChartModel(history, 5);
  assert.equal(ticks.length, 5);
  assert.equal(formatTickDate(new Date(ticks[0])), "Jun 1");
  assert.equal(formatTickDate(new Date(ticks.at(-1))), "Jun 20");
});
