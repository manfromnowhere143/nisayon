import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, expect, it, vi } from "vitest";
import { AppAccess, AppAccessButton } from "../src/pwa/AppAccess";
import { UpstreamLine } from "../src/research/UpstreamLine";
import type { ResearchCatalog } from "../src/research/catalog";

let root: Root | undefined, host: HTMLDivElement;
afterEach(async () => {
  await act(async () => root?.unmount());
  host?.remove();
  vi.restoreAllMocks();
  vi.useRealTimers();
});
async function mount(element: React.ReactNode) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => root!.render(element));
}
async function click(selector: string) {
  await act(async () =>
    host.querySelector<HTMLButtonElement>(selector)!.click(),
  );
}

it("offers installation only through an explicit action and restores the app-access opener", async () => {
  const onOpen = vi.fn(),
    prompt = vi.fn(async () => {});
  await mount(
    <>
      <AppAccessButton />
      <AppAccess onOpen={onOpen} />
    </>,
  );
  const offered = Object.assign(
    new Event("beforeinstallprompt", { cancelable: true }),
    { prompt, userChoice: Promise.resolve({ outcome: "dismissed" }) },
  );
  await act(async () => window.dispatchEvent(offered));
  expect(offered.defaultPrevented).toBe(true);
  expect(prompt).not.toHaveBeenCalled();
  const opener = host.querySelector<HTMLButtonElement>(".app-access-button")!;
  await act(async () => {
    opener.focus();
    opener.click();
  });
  expect(onOpen).toHaveBeenCalledOnce();
  expect(host.querySelector("dialog")?.textContent).toContain(
    "Install Nisayon",
  );
  await click(".research-action");
  expect(prompt).toHaveBeenCalledOnce();
  expect(host.querySelector('[role="status"]')?.textContent).toContain(
    "install later",
  );
  await click(".glass-card-close");
  expect(document.activeElement).toBe(opener);
});

it("provides installation guidance when the browser has no install-prompt event", async () => {
  await mount(
    <>
      <AppAccessButton />
      <AppAccess onOpen={() => {}} />
    </>,
  );
  await click(".app-access-button");
  expect(host.querySelector(".app-install-paths")?.textContent).toContain(
    "Add to Home Screen",
  );
  expect(host.querySelector(".research-action")).toBeNull();
  await click(".workspace-tabs button:last-child");
  expect(host.textContent).toContain("Offline storage is not available yet");
  expect(host.textContent).toContain("Robot recordings, historical catalogs");
});

it("does not consume the same install offer twice during rapid activation", async () => {
  let finish!: () => void;
  const prompt = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
  await mount(<><AppAccessButton /><AppAccess onOpen={() => {}} /></>);
  const offered = Object.assign(new Event("beforeinstallprompt", { cancelable: true }), {
    prompt, userChoice: Promise.resolve({ outcome: "dismissed" }),
  });
  await act(async () => window.dispatchEvent(offered));
  await click(".app-access-button");
  const button = host.querySelector<HTMLButtonElement>(".research-action")!;
  await act(async () => { button.click(); button.click(); });
  expect(prompt).toHaveBeenCalledOnce();
  expect(button.disabled).toBe(true);
  await act(async () => finish());
  expect(host.textContent).toContain("install later");
});

const records: ResearchCatalog["upstream"] = [
  {
    title: "Merged correction",
    status: "merged",
    date: "2026-10-17",
    url: "https://example.test/merge",
    source: { path: "merge.json", sha256: "a".repeat(64), bytes: 1 },
  },
  {
    title: "Released correction",
    status: "released",
    date: "2026-10-12",
    url: "https://example.test/release",
    source: { path: "release.json", sha256: "b".repeat(64), bytes: 1 },
  },
];
it("rotates retained upstream links but pauses on focus, explicit pause and hidden documents", async () => {
  vi.useFakeTimers();
  vi.spyOn(document, "hidden", "get").mockReturnValue(false);
  await mount(<UpstreamLine records={records} />);
  await act(async () => vi.advanceTimersByTime(8000));
  expect(host.querySelector("a")!.href).toContain("/release");
  await act(async () => host.querySelector<HTMLAnchorElement>("a")!.focus());
  await act(async () => vi.advanceTimersByTime(16000));
  expect(host.querySelector("a")!.href).toContain("/release");
  await click('[aria-label="Pause upstream rotation"]');
  await act(async () => host.querySelector<HTMLAnchorElement>("a")!.blur());
  await act(async () => vi.advanceTimersByTime(16000));
  expect(host.querySelector("a")!.href).toContain("/release");
  await click('[aria-label="Next upstream change"]');
  expect(host.querySelector("a")!.href).toContain("/merge");
  await click('[aria-label="Resume upstream rotation"]');
  vi.spyOn(document, "hidden", "get").mockReturnValue(true);
  await act(async () => document.dispatchEvent(new Event("visibilitychange")));
  await act(async () => vi.advanceTimersByTime(16000));
  expect(host.querySelector("a")!.href).toContain("/merge");
});

it("uses manual upstream selection under reduced motion", async () => {
  vi.useFakeTimers();
  const match = window.matchMedia;
  vi.spyOn(window, "matchMedia").mockImplementation((query) => ({
    ...match(query),
    matches: true,
  }));
  await mount(<UpstreamLine records={records} />);
  await act(async () => vi.advanceTimersByTime(24000));
  expect(host.querySelector("a")!.href).toContain("/merge");
  expect(
    host.querySelector('[aria-label="Pause upstream rotation"]'),
  ).toBeNull();
  await click('[aria-label="Next upstream change"]');
  expect(host.querySelector("a")!.href).toContain("/release");
});
