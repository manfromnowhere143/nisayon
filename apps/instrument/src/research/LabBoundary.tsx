import { Component, type ReactNode } from "react";

export function isModuleLoadError(error: unknown): boolean {
  return (
    error instanceof Error &&
    /dynamically imported module|module script|module.*fetch|importing a module|loading chunk|preload css/i.test(
      error.message,
    )
  );
}

/** A failed lazy chunk must leave the shared navigation usable, including
 * when an installed research workspace is opened without a connection. */
export class LabBoundary extends Component<
  { children: ReactNode; onUnavailable: () => void },
  { error: Error | null }
> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) {
    return { error };
  }
  componentDidCatch(error: Error) {
    console.error("Nisayon robot lab could not open", error);
    this.props.onUnavailable();
  }
  render() {
    if (!this.state.error) return this.props.children;
    const module = isModuleLoadError(this.state.error);
    return (
      <main className="lab-unavailable" role="alert">
        <p className="research-micro">Recorded robot lab</p>
        <h1>
          {module
            ? "The lab needs a fresh connection."
            : "The lab could not open."}
        </h1>
        <p>
          {module
            ? "The recording tools could not be retrieved. Reconnect, then close all Nisayon tabs and reopen the instrument to load one complete version."
            : "The lab encountered an error while opening. Reload to try again."}{" "}
          System and Investigate remain available below.
        </p>
        <button className="quiet" onClick={() => location.reload()}>
          Reload the instrument
        </button>
      </main>
    );
  }
}
