// Hairline marks in one stroke weight. No filled shapes except the play mark.

interface Props {
  name: "prev" | "next" | "play" | "pause" | "fork" | "inspect" | "ground" | "link" | "close" | "back" | "view";
}

export function Icon({ name }: Props) {
  const common = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (name) {
    case "prev":
      return (
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" {...common}>
          <path d="M14.5 6.5 9 12l5.5 5.5" />
        </svg>
      );
    case "next":
      return (
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" {...common}>
          <path d="M9.5 6.5 15 12l-5.5 5.5" />
        </svg>
      );
    case "play":
      return (
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" {...common}>
          <path d="M8.5 6.2v11.6L17.5 12z" fill="currentColor" stroke="none" />
        </svg>
      );
    case "pause":
      return (
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" {...common}>
          <path d="M9 6.5v11M15 6.5v11" />
        </svg>
      );
    case "fork":
      return (
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" {...common}>
          <path d="M7 5v14M7 12c0-3 2-5 5-5h5M15 5l2 2-2 2" />
          <circle cx="7" cy="5" r="1.4" />
        </svg>
      );
    case "inspect":
      return (
        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" {...common}>
          <circle cx="12" cy="12" r="7.5" />
          <path d="M12 11v5M12 8.2v.3" />
        </svg>
      );
    case "ground":
      return (
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...common}>
          <circle cx="12" cy="12" r="7.5" />
          <path d="M12 4.5v15A7.5 7.5 0 0 0 12 4.5z" fill="currentColor" stroke="none" />
        </svg>
      );
    case "link":
      return (
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...common}>
          <path d="M10 14a4 4 0 0 0 5.7 0l2.6-2.6a4 4 0 0 0-5.7-5.7L11.5 6.8" />
          <path d="M14 10a4 4 0 0 0-5.7 0l-2.6 2.6a4 4 0 0 0 5.7 5.7l1.1-1.1" />
        </svg>
      );
    case "close":
      return (
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...common}>
          <path d="M7 7l10 10M17 7 7 17" />
        </svg>
      );
    case "back":
      return (
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...common}>
          <path d="M14.5 6.5 9 12l5.5 5.5M9 12h9" />
        </svg>
      );
    case "view":
      return (
        <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" {...common}>
          <path d="M4 9l8-4 8 4-8 4z" />
          <path d="M4 9v6l8 4 8-4V9M12 13v6" />
        </svg>
      );
    default:
      return null;
  }
}
