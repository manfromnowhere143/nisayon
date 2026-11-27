import { WorkspaceMenu, type WorkspaceAction } from "../ui/WorkspaceMenu";
import { WorkspaceNavigation } from "../ui/WorkspaceNavigation";
import type { ResearchRoute } from "./navigation";

type Surface = ResearchRoute["surface"];
/** Navigation and playback have separate ownership and no shared backing.
 * The lab's contextual workspace menu supplies its own navigation. */
export function InstrumentDock({
  surface,
  loading,
  navigate,
  transportHost,
  prepareConcepts,
  utilities,
}: {
  surface: Surface;
  loading: boolean;
  navigate: (surface: Surface) => void;
  transportHost: (host: HTMLDivElement | null) => void;
  prepareConcepts?: () => void;
  utilities?: WorkspaceAction[];
}) {
  const playback = surface === "lab" && !loading;
  const section =
    surface === "qualify"
      ? "develop"
      : surface === "research" || surface === "checks"
        ? "system"
        : surface;
  return (
    <>
      <div
        ref={transportHost}
        className="instrument-playback-host"
        hidden={!playback}
        inert={!playback}
      />
      {surface !== "lab" || loading ? (
        <div className="instrument-navigation" data-surface={surface}>
          <WorkspaceMenu
            label="Workspace"
            onOpen={prepareConcepts}
            navigation={<WorkspaceNavigation current={section} navigate={navigate} prepareRicci={prepareConcepts} />}
            actions={utilities}
          />
        </div>
      ) : null}
    </>
  );
}
