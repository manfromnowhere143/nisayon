// Opposed circular turns (13 and 8 units) joined by a tangent. The open path
// reads as an N and as a trajectory; its shape never encodes a run's status.
export const BRAND_PATH = "M21 76V34A13 13 0 0 1 45.2583 27.5L61.0718 54.89A8 8 0 0 0 76 50.89V21";

export function BrandMark({ className, size = 30 }: { className?: string; size?: number } = {}) {
  return <svg className={className} viewBox="0 0 96 96" width={size} height={size} aria-hidden="true" focusable="false"><path d={BRAND_PATH} fill="none" stroke="currentColor" strokeWidth="8" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
