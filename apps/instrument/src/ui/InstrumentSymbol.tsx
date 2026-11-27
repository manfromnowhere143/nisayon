import type { SVGProps } from "react";

export type InstrumentSymbolName =
  | "lab"
  | "motion"
  | "brain"
  | "parts"
  | "film"
  | "close"
  | "workspace"
  | "view"
  | "study"
  | "sources"
  | "recording"
  | "device"
  | "more";
/** Small purpose-drawn symbols. Labels carry the accessible name; geometry is
 * decorative and shares a single optical weight at ordinary control sizes. */
export function InstrumentSymbol({
  name,
  ...props
}: SVGProps<SVGSVGElement> & { name: InstrumentSymbolName }) {
  return (
    <svg
      viewBox="0 0 36 36"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {name === "lab" ? (
        <>
          <path d="M6 29V9l14-5 10 6v19M6 9l14 5 10-4M20 14v15M4 30h28M11 26l5-2 8 2M13 24v-6l5-3" />
          <circle cx="13" cy="18" r="1.8" />
        </>
      ) : null}
      {name === "motion" ? (
        <>
          <path d="M7 28l9-11 13 5" />
          <path d="M16 17l5-12" opacity=".4" />
          <path d="M24 6a15 15 0 0 1 8 12" opacity=".6" />
          <circle cx="7" cy="28" r="2.4" />
          <circle cx="16" cy="17" r="2.8" />
          <circle cx="29" cy="22" r="2.4" />
        </>
      ) : null}
      {name === "brain" ? <>
        <path d="M18 7c-2-4-8-3-9 1-4 0-6 5-4 8-3 3-1 8 3 9 0 5 6 7 10 3M18 7c2-4 8-3 9 1 4 0 6 5 4 8 3 3 1 8-3 9 0 5-6 7-10 3M18 7v21"/>
        <path d="M9 8c-1 4 1 6 4 6M5 16c4-2 8 0 8 4M8 25c0-4 3-5 5-5M27 8c1 4-1 6-4 6M31 16c-4-2-8 0-8 4M28 25c0-4-3-5-5-5M18 12l-3 3m3 8-3 2m3-13 3 3m-3 8 3 2" opacity=".65"/>
      </> : null}
      {name === "parts" ? (
        <>
          <path d="M18 2v32" opacity=".45" />
          {[7, 17, 27].map((y) => (
            <g key={y}>
              <ellipse cx="18" cy={y} rx="9" ry="3" />
              <path d={`M9 ${y}v3c0 4 18 4 18 0v-3M15 ${y - 1}h6`} />
            </g>
          ))}
        </>
      ) : null}
      {name === "film" ? (
        <path d="M4 11V7h8M24 7h8v4M4 25v4h8M24 29h8v-4M15 12l9 6-9 6Z" />
      ) : null}
      {name === "workspace" ? <path d="m10 14 8-5 8 5v9l-8 5-8-5Zm0 0 8 5 8-5M18 19v9" /> : null}
      {name === "view" ? <><circle cx="18" cy="9" r="3" /><path d="m13 17 5-3 5 3-2 8h-6ZM8 12c-6 4-6 10 0 14m20-14c6 4 6 10 0 14M12 29c4 2 8 2 12 0" /><circle cx="7" cy="11" r="1.5" /><circle cx="29" cy="27" r="1.5" /></> : null}
      {name === "close" ? <path d="m11 11 14 14M25 11 11 25" /> : null}
      {name === "study" ? <><path d="M6 8h10l2 3 2-3h10v21H20l-2 2-2-2H6ZM18 11v20M10 14h4M10 19h4M22 14h4M22 19h4" /></> : null}
      {name === "sources" ? <><path d="M10 4h12l6 6v22H10ZM22 4v7h6M15 17h8M15 22h8M15 27h5M6 8v21" /></> : null}
      {name === "recording" ? <><path d="M5 7h26v22H5ZM5 12h26M10 7v5M15 7v5M21 7v5M26 7v5M15 17l8 4-8 4Z" /></> : null}
      {name === "device" ? <><rect x="9" y="4" width="18" height="28" rx="4" /><path d="M15 27h6M18 10v10m-4-4 4 4 4-4" /></> : null}
      {name === "more" ? <><circle cx="8" cy="18" r="1.5" /><circle cx="18" cy="18" r="1.5" /><circle cx="28" cy="18" r="1.5" /></> : null}
    </svg>
  );
}
