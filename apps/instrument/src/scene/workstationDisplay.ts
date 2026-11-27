import type { WorkstationReading } from "../model/workstation";
import { createCanvasDisplay } from "./canvasDisplay";
import { contactPair, type ContactView } from "../lab/contactData";

type ContactReading = { instrument: "contact"; identity: string; view: ContactView };
type DisplayReading = WorkstationReading | ContactReading;
export function contactWorkstationReading(view: ContactView): ContactReading {
  return { instrument: "contact", identity: `${view.packet.packet_sha256}:${view.condition}:${view.index}`, view };
}

const W = 768, H = 480;
const ink = "#e8f0f3", quiet = "#94a8b4", accent = "#a9d9dc";
const number = (n: number | null, digits: number) => n === null ? "—" : n.toFixed(digits).replace("-", "−");

/** All sizes are in one small design space. The texture is display-referred,
 * with no tone mapping or synthetic bloom; opening it uses semantic HTML. */
export function drawWorkstation(ctx: CanvasRenderingContext2D, reading: DisplayReading | null) {
  if (reading && "instrument" in reading) { drawContactWorkstation(ctx,reading.view); return; }
  ctx.save();
  ctx.scale(ctx.canvas.width / W, ctx.canvas.height / H);
  ctx.fillStyle = "#091218"; ctx.fillRect(0, 0, W, H);
  const text = (value: string, x: number, y: number, size = 20, colour = ink, weight = 400, maxWidth = W - x - 34) => {
    ctx.font = `${weight} ${size}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.fillStyle = colour; ctx.textAlign = "left"; ctx.fillText(value, x, y, maxWidth);
  };
  if (!reading) {
    text("NISAYON", 38, 57, 17, quiet, 500);
    text("Recording desk", 38, 205, 42);
    text("Select an experiment", 38, 243, 20, quiet);
    ctx.restore(); return;
  }
  const { series, status } = reading;
  text("RECORDED", 38, 37, 15, accent, 500);
  text(reading.caseLabel, 38, 74, 26, ink, 500, 440);
  text(reading.runLabel, 525, 74, 20, quiet, 400, 208);
  if (status === "loading") text("Selecting · showing current recording", 38, 108, 17, "#d9c9a4");
  else text(status === "unavailable" ? "Sample unavailable" : `Step ${reading.step} / ${Math.max(0, reading.count - 1)}`, 38, 108, 17, quiet);
  text(series.label, 38, 154, 18, quiet);
  text(number(reading.value, series.kind === "command" ? 3 : 1), 34, 222, 65, ink, 400, 360);
  text(series.unit, 38, 249, 16, quiet);
  text(series.kind === "command" ? "Intended" : "Recorded limit", 500, 154, 18, quiet);
  text(number(reading.comparison, series.kind === "command" ? 3 : 1), 496, 217, 48, quiet, 400, 240);

  const x = (time: number) => 38 + 692 * (time - series.start) / Math.max(1e-9, series.end - series.start);
  const range = Math.max(1e-9, series.max - series.min);
  const y = (value: number) => 368 - 82 * (value - series.min) / range;
  ctx.strokeStyle = "#283841"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(38, 380); ctx.lineTo(730, 380); ctx.stroke();
  if (status !== "unavailable") {
    if (series.reference !== null) {
      ctx.setLineDash([3, 6]); ctx.strokeStyle = "#6a838b";
      ctx.beginPath(); ctx.moveTo(38, y(series.reference)); ctx.lineTo(730, y(series.reference)); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.strokeStyle = accent; ctx.lineWidth = 1.8;
    ctx.beginPath();
    let previous: { x: number; value: number } | null = null;
    for (const column of series.columns) {
      const px = x(column.time);
      if (column.min !== null && column.max !== null) { ctx.moveTo(px, y(column.min)); ctx.lineTo(px, y(column.max)); }
      if (previous && !column.gap && column.first !== null) { ctx.moveTo(previous.x, y(previous.value)); ctx.lineTo(px, y(column.first)); }
      previous = column.gap || column.last === null ? null : { x: px, value: column.last };
    }
    ctx.stroke();
    if (reading.signalTime !== null && reading.value !== null) {
      const px = x(reading.signalTime), py = y(reading.value);
      ctx.strokeStyle = "#69818b"; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(px, 275); ctx.lineTo(px, 380); ctx.stroke();
      ctx.fillStyle = ink; ctx.beginPath(); ctx.arc(px, py, 4, 0, Math.PI * 2); ctx.fill();
    }
  }
  text(`${series.kind === "height" ? "Result" : "Action"}  ${number(reading.signalTime, 2)} s`, 38, 423, 19);
  text(`Robot · ${reading.phase}  ${number(reading.time, 2)} s`, 434, 423, 18, quiet);
  text("Open evidence  ↗", 38, 457, 16, quiet);
  ctx.restore();
}

// The display and floating workbench read the same exact retained rows. No
// independent scientific calculation, execution clock or decision lives here.
function drawContactWorkstation(ctx: CanvasRenderingContext2D, view: ContactView) {
  const pair = contactPair(view), candidate = pair.candidate?.rows[view.index], reference = pair.reference?.rows[view.index];
  ctx.save(); ctx.scale(ctx.canvas.width/W,ctx.canvas.height/H);
  ctx.fillStyle = "#091218"; ctx.fillRect(0,0,W,H);
  const text = (label: string, x: number, y: number, size = 20, colour = ink) => {
    ctx.font = `${size}px -apple-system, BlinkMacSystemFont, sans-serif`;
    ctx.fillStyle = colour; ctx.fillText(label,x,y,W-x-30);
  };
  text("RETAINED SIMULATION",38,37,15,accent);
  text("Contact dynamics",38,78,30);
  text(`${view.packet.experiment.spec.parameters[view.condition+"_force_n"]} N · prescribed input`,38,111,18,quiet);
  text("Candidate position · m",38,164,18,"#e0c5a0");
  text(number(candidate?.x_m ?? null,4),34,223,56);
  text("Reference · m",470,164,18,"#b9d4e3");
  text(number(reference?.x_m ?? null,4),466,223,48,quiet);
  const traces = [pair.reference,pair.candidate];
  const end = Math.max(.005,...traces.map(t=>t?.rows.at(-1)?.t_s ?? 0));
  const max = Math.max(.001,...traces.flatMap(t=>t?.rows.map(r=>r.x_m) ?? []));
  const x = (t:number)=>38+692*t/end, y=(m:number)=>371-95*m/max;
  ctx.strokeStyle="#283841"; ctx.lineWidth=1; ctx.beginPath(); ctx.moveTo(38,380); ctx.lineTo(730,380); ctx.stroke();
  traces.forEach((trace,i)=>{
    if (!trace) return;
    ctx.strokeStyle=i===0?"#b9d4e3":"#e0c5a0"; ctx.lineWidth=1.8; ctx.setLineDash(i===0?[5,4]:[]); ctx.beginPath();
    trace.rows.forEach((r,j)=>{ if(j) ctx.lineTo(x(r.t_s),y(r.x_m)); else ctx.moveTo(x(r.t_s),y(r.x_m)); }); ctx.stroke();
    const row=trace.rows[view.index]; if(row) { ctx.fillStyle=ctx.strokeStyle; ctx.beginPath(); ctx.arc(x(row.t_s),y(row.x_m),4,0,Math.PI*2); ctx.fill(); }
  });
  ctx.setLineDash([]);
  text(`Exact row ${view.index} · ${number(candidate?.t_s ?? reference?.t_s ?? null,3)} s`,38,422,19);
  text("Inspect experiment  ↗",38,457,16,quiet); ctx.restore();
}

export function createWorkstationDisplay(canvas: HTMLCanvasElement, width: 512 | 768 = 768) {
  return createCanvasDisplay<DisplayReading>(canvas, width, "Selected experiment display", drawWorkstation,
    (a, b) => a.identity === b.identity && ("instrument" in a && "instrument" in b || !("instrument" in a) && !("instrument" in b) && a.status === b.status && a.series === b.series),
    reading => reading.identity);
}
