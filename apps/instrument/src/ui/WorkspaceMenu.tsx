import {
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import "../styles/workspace-menu.css";
import { InstrumentSymbol, type InstrumentSymbolName } from "./InstrumentSymbol";
import { Icon } from "./Icon";
import { workspacePlacement } from "./workspacePlacement";

export interface WorkspaceAction {
  id: string;
  label: string;
  icon: ReactNode;
  title?: string;
  pressed?: boolean;
  onSelect?: () => void;
  content?: ReactNode;
}

/** Native top-layer disclosure. Navigation and tools share one vertical rail;
 * only appearance sits beside the invoker. */
export function WorkspaceMenu({
  children,
  active = true,
  className = "",
  label,
  title = "Workspace",
  symbol = "workspace",
  icon,
  onOpen,
  navigation,
  actions,
  placement = "auto",
  popoverClassName = "",
  closeOnSelect = true,
}: {
  children?: ReactNode;
  active?: boolean;
  className?: string;
  label?: string;
  title?: string;
  symbol?: InstrumentSymbolName;
  icon?: ReactNode;
  onOpen?: (() => void) | undefined;
  navigation?: ReactNode;
  actions?: WorkspaceAction[] | undefined;
  placement?: "auto" | "above" | "above-center";
  popoverClassName?: string;
  closeOnSelect?: boolean;
}) {
  const id = useId(),
    trigger = useRef<HTMLButtonElement>(null),
    panel = useRef<HTMLDivElement>(null),
    toolsTrigger = useRef<HTMLButtonElement>(null),
    backTrigger = useRef<HTMLButtonElement>(null),
    railFocus = useRef<"tools" | "navigation" | null>(null);
  const [open, setOpen] = useState(false);
  const [toolsOpen, setToolsOpen] = useState(false);
  const appearance = actions?.find(item => item.id === "appearance");
  const utilities = actions?.filter(item => item.id !== "appearance") ?? [];
  const close = () => {
    if (panel.current?.hidePopover && panel.current.matches(":popover-open"))
      panel.current.hidePopover();
  };
  const place = () => {
    const node = panel.current,
      button = trigger.current;
    if (!node || !button) return;
    const view = window.visualViewport,
      left = view?.offsetLeft ?? 0,
      top = view?.offsetTop ?? 0;
    const safe = getComputedStyle(document.documentElement);
    const inset = (edge: string) => parseFloat(safe.getPropertyValue(`--safe-${edge}`)) || 0;
    const box = button.getBoundingClientRect();
    const viewport = { left, top, width: view?.width ?? innerWidth, height: view?.height ?? innerHeight };
    const insets = { left: inset("left"), right: inset("right"), top: inset("top"), bottom: inset("bottom") };
    const requestedWidth = navigation ? (appearance ? 96 : 48) : actions ? 48 : placement === "above-center" ? 288 : 312;
    const side = navigation ? "rail" : placement;
    // Measure at the new width without the previous viewport's height cap.
    // This runs on disclosure/resize, never in the scene's render loop.
    node.style.width = `${workspacePlacement(box, viewport, insets, requestedWidth, 0, side).width}px`;
    node.style.maxHeight = "none";
    const bounds = workspacePlacement(box, viewport, insets, requestedWidth, node.scrollHeight, side);
    Object.assign(node.style, {
      width: `${bounds.width}px`,
      left: `${bounds.left}px`,
      top: `${bounds.top}px`,
      maxHeight: `${bounds.maxHeight}px`,
    });
    node.style.setProperty("--workspace-available-height", `${bounds.maxHeight}px`);
  };
  useLayoutEffect(() => { if (!active) close(); }, [active]);
  useLayoutEffect(() => {
    if (!railFocus.current) return;
    const target = railFocus.current === "tools" ? backTrigger.current : toolsTrigger.current;
    target?.closest(".workspace-rail-list")?.scrollTo?.({ top: 0 });
    target?.focus({ preventScroll: true });
    railFocus.current = null;
  }, [toolsOpen]);
  useLayoutEffect(() => {
    if (!open) return;
    place();
    const resize = new ResizeObserver(place);
    if (trigger.current) resize.observe(trigger.current);
    window.addEventListener("resize", place);
    window.visualViewport?.addEventListener("resize", place);
    window.visualViewport?.addEventListener("scroll", place);
    window.addEventListener("popstate", close);
    return () => {
      resize.disconnect();
      window.removeEventListener("resize", place);
      window.visualViewport?.removeEventListener("resize", place);
      window.visualViewport?.removeEventListener("scroll", place);
      window.removeEventListener("popstate", close);
    };
  }, [open, toolsOpen, !!appearance, placement]);
  const action = (item: WorkspaceAction) => item.content ? (
    <WorkspaceMenu key={item.id} label={item.label} title={item.label} icon={item.icon} className="workspace-tool">
      {item.content}
    </WorkspaceMenu>
  ) : (
    <button type="button" key={item.id} className={`workspace-tool${item.id === "appearance" ? " workspace-appearance" : ""}`} aria-label={item.label} title={item.title ?? item.label} aria-pressed={item.pressed} onClick={item.onSelect}>
      {item.icon}
      <span className="sr-only">{item.title ?? item.label}</span>
    </button>
  );
  return <>
    <button ref={trigger} className={`workspace-menu ${className}`} data-workspace-navigation={navigation ? "true" : undefined} popoverTarget={id} aria-haspopup="dialog" aria-expanded={open} aria-controls={id} aria-label={label ?? "Workspace controls"} title={label ?? "Workspace controls"} onClick={place}>
      {icon ?? <InstrumentSymbol name={symbol} />}
      <span className="sr-only">{label ?? "Workspace controls"}</span>
    </button>
    <div ref={panel} id={id} popover="auto" role="dialog" aria-label={toolsOpen ? "Workspace tools" : title} className={`workspace-popover ${popoverClassName}${navigation ? " workspace-popover-rail" : actions ? " workspace-popover-actions" : ""}`} onToggle={event => {
      if (event.target !== event.currentTarget) return;
      setOpen(event.newState === "open");
      if (event.newState === "open") onOpen?.();
      else { railFocus.current = null; setToolsOpen(false); }
    }}>
      {!navigation && !actions ? <header><span>{title}</span><button type="button" onClick={close} aria-label={`Close ${title}`}><InstrumentSymbol name="close" /></button></header> : null}
      <div className={`workspace-popover-content${actions && !navigation ? " workspace-actions-list" : ""}`} onClick={event => {
        const target = event.target as Element;
        const button = target.closest("button");
        if (closeOnSelect && button && !button.hasAttribute("popovertarget") && !button.hasAttribute("data-workspace-disclosure") && (navigation || target.closest("[popover]") === panel.current)) close();
      }}>
        {navigation ? <>
          {appearance ? <div className="workspace-tool-rail" role="group" aria-label="Appearance">
            {action(appearance)}
          </div> : null}
          <div className="workspace-rail-list" hidden={toolsOpen} inert={toolsOpen}>
            {navigation}
            {utilities.length ? <button ref={toolsTrigger} type="button" className="workspace-tool workspace-tools-trigger" aria-label="Tools" title="Tools" aria-controls={`${id}-tools`} aria-expanded={toolsOpen} data-workspace-disclosure onClick={() => { railFocus.current = "tools"; setToolsOpen(true); }}>
              <InstrumentSymbol name="more" />
            </button> : null}
          </div>
          {utilities.length ? <div id={`${id}-tools`} className="workspace-rail-list workspace-tools-list" hidden={!toolsOpen} inert={!toolsOpen} role="group" aria-label="Contextual tools">
            <button ref={backTrigger} type="button" className="workspace-tool" aria-label="Back to navigation" title="Back to navigation" data-workspace-disclosure onClick={() => { railFocus.current = "navigation"; setToolsOpen(false); }}><Icon name="back" /></button>
            {utilities.map(action)}
          </div> : null}
        </> : actions ? actions.map(action) : children}
      </div>
    </div>
  </>;
}
