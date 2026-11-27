let pending: Promise<typeof import("./ConceptStudio")> | undefined;
let prepared: typeof import("./ConceptStudio") | undefined;

/** Navigation intent warms code only. It never allocates a hidden renderer. */
export function loadRicci() {
  return (pending ??= import("./ConceptStudio")
    .then((value) => {
      prepared = value;
      return value;
    })
    .catch((error) => {
      pending = undefined;
      throw error;
    }));
}
export function preparedRicci() {
  return prepared?.ConceptStudio ?? null;
}
export function prepareRicci() {
  void loadRicci().catch(() => {});
}
