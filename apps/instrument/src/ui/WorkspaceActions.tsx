import type { Ground } from "../state/ground";
import { Icon } from "./Icon";
import { InstrumentSymbol } from "./InstrumentSymbol";
import type { WorkspaceAction } from "./WorkspaceMenu";

/** The same utility actions and symbols in every workspace. Scene-only
 * operations are supplied by the scene instead of opening unrelated controls. */
export function workspaceUtilities({ ground, toggleGround, copyLink, copyLabel }: {
  ground: Ground;
  toggleGround?: (() => void) | undefined;
  copyLink: () => void;
  copyLabel: string;
}): WorkspaceAction[] {
  return [
    ...(toggleGround ? [{ id: "appearance", label: `Switch to ${ground === "black" ? "paper" : "black"} ground`, icon: <AppearanceSymbol ground={ground} />, onSelect: toggleGround }] : []),
    { id: "link", label: copyLabel, icon: <Icon name="link" />, onSelect: copyLink },
    { id: "device", label: "Nisayon on this device", icon: <InstrumentSymbol name="device" />, onSelect: () => window.dispatchEvent(new Event("nisayon:app-access")) },
  ];
}

/** A small light/dark destination, independent of the navigation glyphs. */
function AppearanceSymbol({ ground }: { ground: Ground }) {
  return <svg className="workspace-appearance-symbol" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {ground === "black" ? <>
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6 7 7m10 10 1.4 1.4M5.6 18.4 7 17M17 7l1.4-1.4" />
    </> : <path d="M19.4 14.7A7.8 7.8 0 0 1 9.3 4.6a7.8 7.8 0 1 0 10.1 10.1Z" />}
  </svg>;
}
