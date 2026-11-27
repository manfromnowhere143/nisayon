import { createCanvasDisplay } from "../scene/canvasDisplay";
import { RICCI_TRACE, tracePose, type TraceCase } from "./ricciTrace";

export function ricciDeskReading(time: number, variant: TraceCase, enabled: boolean) {
  const pose = tracePose(time, variant);
  return { identity: `${RICCI_TRACE.revision}:${variant}:${pose.t}:${enabled}`, time: pose.t, variant, enabled,
    phase: pose.phase.label, liftMm: 120 * pose.lift };
}
type Reading = ReturnType<typeof ricciDeskReading>;
const path = Array.from({ length: 121 }, (_, i) => tracePose(i / 10, "load").lift);

function draw(ctx: CanvasRenderingContext2D, value: Reading | null) {
  const reading = value ?? ricciDeskReading(0, "load", false);
  ctx.save(); ctx.scale(ctx.canvas.width / 768, ctx.canvas.height / 480);
  ctx.fillStyle = "#091218"; ctx.fillRect(0, 0, 768, 480);
  const text = (label: string, x: number, y: number, size = 20, colour = "#e8f0f3") => {
    ctx.font = `400 ${size}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.fillStyle = colour; ctx.fillText(label, x, y, 710 - x);
  };
  text("AUTHORED MOTION", 38, 38, 16, "#a9d9dc");
  text("Ricci", 38, 80, 30);
  text(reading.variant === "load" ? "Shifting tray load" : "Slipping stance foot", 38, 114, 20, "#94a8b4");
  text(reading.enabled ? reading.phase : "Motion study", 38, 179, 28);
  text(`${reading.time.toFixed(1)} s`, 34, 243, 58);
  text("of 12.0 s", 38, 272, 17, "#94a8b4");
  text("Tray lift · authored", 472, 180, 18, "#94a8b4");
  text(reading.enabled ? `${reading.liftMm.toFixed(0)} mm` : "—", 470, 239, 42);
  ctx.strokeStyle = "#a9d9dc"; ctx.lineWidth = 1.8; ctx.beginPath();
  path.forEach((lift, i) => { const x = 38 + i / 120 * 692, y = 367 - lift * 65; if (!i) ctx.moveTo(x, y); else ctx.lineTo(x, y); });
  ctx.stroke();
  const x = 38 + reading.time / 12 * 692;
  ctx.strokeStyle = "#69818b"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(x, 290); ctx.lineTo(x, 380); ctx.stroke();
  text("Preview geometry · no measured outcome", 38, 422, 18, "#94a8b4");
  text("Open motion study  ↗", 38, 457, 17, "#94a8b4");
  ctx.restore();
}

export function createRicciWorkstation(canvas: HTMLCanvasElement, width: 512 | 768) {
  return createCanvasDisplay(canvas, width, "Ricci authored motion display", draw, (a, b) => a.identity === b.identity, value => value.identity);
}
