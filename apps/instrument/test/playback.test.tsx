import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { expect, it } from "vitest";
import { playbackRow } from "../src/model/playback";
import type { SampleRow } from "../src/model/types";
import { SectionDeck } from "../src/ui/RecordPages";

const clocks = (times: [number, number][]) => times.map(([action_sim_time_s, next_sim_time_s]) => ({ action_sim_time_s, next_sim_time_s }) as SampleRow);

it("holds retained poses through recording gaps and selects on the chosen phase's own timestamps", () => {
  const rows = clocks([[10, 10.05], [10.05, 10.4], [10.4, 10.45], [10.45, 10.5]]);
  expect(playbackRow(rows, "before", 0, 0.2)).toBe(1);
  expect(playbackRow(rows, "after", 0, 0.2)).toBe(0);
  expect(playbackRow(rows, "before", 0, 0.4)).toBe(2);
  expect(playbackRow(rows, "after", 0, 0.35)).toBe(1);
  expect(playbackRow(rows, "after", 2, -1)).toBe(2);
  expect(playbackRow(rows, "after", 2, 20)).toBe(3);
  expect(playbackRow([], "after", 0, 20)).toBe(0);
});

it("catches up after a delayed display frame without accumulating drift or queuing stale poses", () => {
  const rows = clocks(Array.from({ length: 400 }, (_, index) => [index * 0.05, (index + 1) * 0.05]));
  expect(playbackRow(rows, "before", 30, 0.017)).toBe(30);
  expect(playbackRow(rows, "before", 30, 0.367)).toBe(37);
  expect(playbackRow(rows, "before", 30, 1.017)).toBe(50);
  expect(playbackRow(rows, "before", 30, 17.017)).toBe(370);
  expect(playbackRow(rows, "before", 30, 25)).toBe(399);
});

it("keeps inactive panel state without redoing its row work, then reveals current readings immediately", async () => {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const renders: Record<string, number> = { signals: 0, spatial: 0 };
  function Reading({ name, row }: { name: string; row: number }) {
    renders[name]!++;
    const [precision, setPrecision] = useState(false);
    return <button data-reading={name} onClick={() => setPrecision(!precision)}>{row} · {precision ? "precise" : "compact"}</button>;
  }
  const render = async (row: number) => act(async () => root.render(<SectionDeck label="Readings" sections={[
    { id: "signals", label: "Signals", content: <Reading name="signals" row={row} /> },
    { id: "spatial", label: "Spatial", content: <Reading name="spatial" row={row} /> },
  ]} />));
  const select = async (name: string) => act(async () => Array.from(container.querySelectorAll<HTMLButtonElement>(".section-tab")).find((button) => button.textContent === name)!.click());
  try {
    await render(0);
    await act(async () => container.querySelector<HTMLButtonElement>('[data-reading="signals"]')!.click());
    await select("Spatial");
    const hiddenRenders = renders.signals;
    for (const row of [1, 5, 10, 64]) await render(row);
    expect(renders.signals).toBe(hiddenRenders);
    expect(container.querySelector('.deck-panel:not([hidden]) [data-reading]')!.textContent).toBe("64 · compact");
    await select("Signals");
    expect(container.querySelector('.deck-panel:not([hidden]) [data-reading]')!.textContent).toBe("64 · precise");
  } finally {
    await act(async () => root.unmount());
    container.remove();
  }
});
