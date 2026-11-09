// ui.js -- the controls: the search box, dragging, zooming, pinching, the tip, the mode and layer switches, resizing; load() at the end
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { S } from "./state.js";
import { mode, bioLayer, legend } from "./style.js";
import { $, canvas, tilt, points, on, MAX_ZOOM, fmt, fmtPop } from "./state.js";
import { setup } from "./geom.js";
import { yearText, showDay, histDay, setDay, pxKm } from "./history.js";
import { query, draw } from "./view.js";
import { shown, visible } from "./labels.js";
import { wanted, load } from "./data.js";
import { search } from "./search.js";
import { flagCode, flagSvg } from "./flags.js";
import { clearSel, select, identify } from "./select.js";
import { groupClick, renderGroups, game } from "./groups.js";
import { gameClick } from "./game.js";

// ---- the search box ------------------------------------------------------------------------------------------------
S.found = []; S.cursor = -1;
export function showResults() {
  const ul = $("results"); ul.innerHTML = "";
  S.found.forEach((e, i) => {
    const li = document.createElement("li");
    li.className = i === S.cursor ? "on" : "";
    const name = Object.assign(document.createElement("span"), { textContent: e.name });
    name.insertAdjacentHTML("afterbegin", flagSvg(flagCode(e), 11, { cls: "fl", outline: false }));
    li.append(name, Object.assign(document.createElement("span"), { textContent: e.kind }));
    li.onmousedown = (ev) => { ev.preventDefault(); choose(i); };
    ul.append(li);
  });
}
export function choose(i) { const e = S.found[i]; if (!e) return; S.found = []; S.cursor = -1; showResults(); $("q").value = e.name; $("q").blur(); select(e); }
S.typing = null;   // (searched once the typing pauses: a phone does not search again under every letter)
export const searchNow = () => { clearTimeout(S.typing); S.typing = null; S.found = search($("q").value); S.cursor = S.found.length ? 0 : -1; showResults(); };
// ---- moving: drag turns the globe (every projection is rotated the same way), the wheel zooms about the place under the
// cursor (about the centre with the cursor off the map, in space), a pinch about the centre. The map is drawn as it moves -- from a coarser copy, without labels -- once a frame, at where it has got to: a
// draw that takes longer than a frame is followed, when it ends, by one at where the map has moved since (the moves
// meanwhile are one draw, not many). Drawn whole (its labels, its own copy) once the movement pauses for 160 ms or ends.
S.drag = null; S.idle = null; S.moved = 0; S.moving = false; S.frame = 0;
export const still = () => { clearTimeout(S.idle); cancelAnimationFrame(S.frame); S.frame = 0; S.moving = false; draw(); };
export const moveDraw = () => {
  S.moving = true; S.frame ||= requestAnimationFrame(() => { S.frame = 0; draw(true); });
  clearTimeout(S.idle); S.idle = setTimeout(still, 160);
};
// ZOOM (the wheel and a pinch alike)
// `at` (a point on the screen): the place there stays there -- the globe turned after the zoom until it is back under it.
// (Newton's steps on the turn's two angles, the place's offset from `at` the error: a turn moves a place by its own
// longitude and latitude only near the centre, and a flat projection turned obliquely -- Mercator's -- far from it. The zoom
// taken in steps of 5% at most, each solved from the last: in one jump the place can leave across the map's edge, the
// meridian 180° from its middle, and come back on the other side, where no step leads back from)
export function zoomTo(z, at) {
  const ll = at && S.proj.invert(at), p = ll && isFinite(ll[0]) && isFinite(ll[1]) && S.proj(ll);
  const keep = p && Math.hypot(p[0] - at[0], p[1] - at[1]) < 1;   // (on the map: off it a projection's inverse is no place, or another)
  const z0 = S.zoom;
  S.zoom = Math.max(0.5, Math.min(MAX_ZOOM, z)); setup();
  if (keep) {
    const off = (r) => { S.proj.rotate(r); const q = S.proj(ll); return q && isFinite(q[0]) && isFinite(q[1]) ? [q[0] - at[0], q[1] - at[1]] : null; };
    const size = (e) => e ? Math.hypot(e[0], e[1]) : Infinity, h = 1e-4, base = S.proj.scale() / S.zoom;
    const steps = Math.min(100, Math.max(1, Math.ceil(Math.abs(Math.log(S.zoom / z0)) / Math.log(1.05))));
    let r = [S.rotate[0], S.rotate[1], 0];
    for (let st = 1; st <= steps; st++) {
      S.proj.scale(base * z0 * (S.zoom / z0) ** (st / steps));
      let e = off(r);
      for (let i = 0; e && size(e) > 0.01 && i < 20; i++) {
        const a = off([r[0] + h, r[1], 0]), b = off([r[0], r[1] + h, 0]);
        if (!a || !b) break;
        const j00 = (a[0] - e[0]) / h, j01 = (b[0] - e[0]) / h, j10 = (a[1] - e[1]) / h, j11 = (b[1] - e[1]) / h, det = j00 * j11 - j01 * j10;
        if (!det) break;
        let dl = -(j11 * e[0] - j01 * e[1]) / det, dp = -(j00 * e[1] - j10 * e[0]) / det, s = 1, n = null;
        const most = 30 / Math.max(Math.abs(dl), Math.abs(dp), 30); dl *= most; dp *= most;
        for (let k = 0; k < 8; k++, s /= 2) {   // (a step that makes it worse: halved)
          n = [r[0] + dl * s, Math.max(-90, Math.min(90, r[1] + dp * s)), 0];
          if (size(off(n)) < size(e)) break;
          n = null;
        }
        if (!n) break;
        r = n; e = off(r);
      }
    }
    // (no turn keeps it there: on a whole world's Mercator, at its side, the place is so far round that only a globe turned
    //  past the pole -- upside down -- would hold it. The zoom is about the centre then, as off the map)
    S.proj.scale(base * S.zoom);
    if (size(off(r)) < 1) S.rotate = r;
  }
  S.proj.rotate(tilt(S.rotate));
  moveDraw();
}
// THE POINTERS DOWN (a mouse, a pen, each finger): one drags the globe round, two pinch -- the zoom follows the distance
// between them from where the pinch began; lifting one ends the pinch without a click
export const fingers = new Map();
S.pinch = null;   // [the distance between the two at the start, the zoom then]
export const spread = () => { const [a, b] = [...fingers.values()]; return Math.hypot(a[0] - b[0], a[1] - b[1]); };
export const lift = (e, cancelled) => {
  fingers.delete(e.pointerId);
  if (S.pinch) { if (!fingers.size) { S.pinch = null; S.drag = null; canvas.classList.remove("dragging"); still(); } return; }
  const click = !cancelled && S.drag && S.moved < (e.pointerType === "mouse" ? 3 : 8);
  S.drag = null; canvas.classList.remove("dragging"); clearTimeout(S.idle);
  if (click && S.src) { if (game.open) gameClick(e); else if ($("grouping").checked) groupClick(e); else identify(e); } else still();
};
export function tip(e) {
  const t = $("tip");
  if (!S.src || game.open) return;                                  // (the game: no names to go by)
  const ll = S.proj.invert([e.clientX, e.clientY]);
  if (!ll || !isFinite(ll[0])) { t.style.display = "none"; return; }
  const r = 8 * pxKm() / 111, c = Math.max(0.1, Math.cos(ll[1] * Math.PI / 180)), box = [[ll[0] - r / c, ll[1] - r, ll[0] + r / c, ll[1] + r]];
  const best = [];
  for (const [layer, label] of [
    ["cities", (p) => `${p.name}${p.name_local ? " (" + p.name_local + ")" : ""} · ${fmtPop(p.population)}`],
    ["monuments", (p) => `${p.name} · ${p.kind}` + (p.visitors ? ` · ${fmt(p.visitors)} visitors/yr` : "")],
    ["airports", (p) => `${p.name} (${p.iata})` + (p.passengers ? ` · ${fmtPop(p.passengers)} passengers/yr` : "")],
    ["nature", (p) => `${p.name} · ${p.kind}${p.elevation_m != null ? " · " + fmt(p.elevation_m) + " m" : ""}`],
    ["events", (p) => `${p.name} · ${p.kind} · ${showDay(p.date)}`],
  ]) {
    if (!S.src[layer] || !on(layer) || (layer === "events" && !(mode() === "history" && S.src.hist))) continue;
    for (const i of query(points[layer], box)) {
      const f = S.src[layer].features[i];
      if (!visible(f.geometry.coordinates) || !shown(layer, i)) continue;   // (only what is drawn)
      const [x, y] = S.proj(f.geometry.coordinates), d = Math.hypot(x - e.clientX, y - e.clientY);
      if (d < 7) best.push([d, label(f.properties)]);
    }
  }
  best.sort((a, b) => a[0] - b[0]);
  if (!best.length) { t.style.display = "none"; return; }
  t.textContent = best[0][1]; t.style.display = "block"; t.style.left = e.clientX + 12 + "px"; t.style.top = e.clientY + 12 + "px";
}
// the three maps a click apart: the biogeographical one again switches between its biomes and its ecoregions
export function quickShown() {
  for (const b of $("quick").children) b.classList.toggle("on", b.dataset.mode === mode());
  $("quick").lastElementChild.querySelector("span").textContent = mode() === "bio" && bioLayer() === "ecoregions" ? "ecoregions" : "biomes";
}
// the networks over the map and its points a click each (a button its layers' own boxes below: travel is the monuments
// and the airports); a map chosen starts with its own -- the roads and the cities over the political map, the rivers
// and the peaks over the others
export const toggles = () => document.querySelectorAll(".toggles button");
export const layersOf = (b) => b.dataset.layers.split(" ");
export const TOGGLED = { political: ["motorways", "cities"], other: ["rivers", "nature"] };
export function togglesShown() { for (const b of toggles()) { const v = layersOf(b).every(on); b.classList.toggle("on", v); b.setAttribute("aria-pressed", String(v)); } }
export function toggleDefaults() {
  const want = TOGGLED[mode() === "political" ? "political" : "other"];
  for (const b of toggles()) for (const k of layersOf(b)) document.querySelector(`[data-layer="${k}"]`).checked = layersOf(b).some((x) => want.includes(x));
  togglesShown();
}
export function modeChanged(redraw = true) {
  quickShown(); toggleDefaults();
  $("palette").disabled = mode() !== "political" && mode() !== "history";
  $("biolevel").hidden = mode() !== "bio";
  $("histbox").hidden = mode() !== "history";
  legend(); renderGroups(); wanted();
  if (redraw) draw();
}
// (drawn again at a new size -- the window's, or the canvas's as a phone's browser bar slides in or out -- once a frame)
S.resizing = false;
export const resized = () => { if (S.resizing) return; S.resizing = true; requestAnimationFrame(() => { S.resizing = false; setup(); draw(); }); };

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  $("q").addEventListener("input", () => {
    clearTimeout(S.typing);
    if (!$("q").value && S.sel) return clearSel();
    S.typing = setTimeout(searchNow, 120);
  });
  $("q").addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") { S.cursor = Math.min(S.found.length - 1, S.cursor + 1); showResults(); ev.preventDefault(); }
    else if (ev.key === "ArrowUp") { S.cursor = Math.max(0, S.cursor - 1); showResults(); ev.preventDefault(); }
    else if (ev.key === "Enter") { if (S.typing) searchNow(); choose(S.cursor); }   // (Enter before the pause: what was typed, not the last results)
    else if (ev.key === "Escape") { if (S.sel && !S.found.length) clearSel(); S.found = []; showResults(); $("q").blur(); }
  });
  $("q").addEventListener("blur", () => { S.found = []; showResults(); });
  canvas.addEventListener("pointerdown", (e) => {
    fingers.set(e.pointerId, [e.clientX, e.clientY]); canvas.setPointerCapture(e.pointerId);
    if (fingers.size === 2) { S.drag = null; S.moved = 99; S.pinch = [Math.max(spread(), 1), S.zoom]; return; }   // (a second finger: a pinch, never a click)
    if (fingers.size > 2) return;
    S.drag = [e.clientX, e.clientY, ...S.rotate]; S.moved = 0; canvas.classList.add("dragging");
  });
  canvas.addEventListener("pointermove", (e) => {
    if (fingers.has(e.pointerId)) fingers.set(e.pointerId, [e.clientX, e.clientY]);
    if (S.pinch && fingers.size === 2) return zoomTo(S.pinch[1] * spread() / S.pinch[0]);
    if (!S.drag) return e.pointerType === "mouse" ? tip(e) : undefined;
    S.moved = Math.max(S.moved, Math.hypot(e.clientX - S.drag[0], e.clientY - S.drag[1]));
    if (S.moved < (e.pointerType === "mouse" ? 3 : 8)) return;    // (a finger wobbles more than a mouse on a tap)
    const k = 150 / S.proj.scale();
    S.rotate = [S.drag[2] + (e.clientX - S.drag[0]) * k * 0.6, Math.max(-90, Math.min(90, S.drag[3] - (e.clientY - S.drag[1]) * k * 0.6)), 0];
    S.proj.rotate(tilt(S.rotate));
    moveDraw();
  });
  canvas.addEventListener("pointerup", (e) => lift(e, false));
  canvas.addEventListener("pointercancel", (e) => lift(e, true));
  canvas.addEventListener("wheel", (e) => { e.preventDefault(); zoomTo(S.zoom * Math.exp(-e.deltaY * 0.0015), [e.clientX, e.clientY]); }, { passive: false });
  $("proj").onchange = () => { setup(); draw(); };
  for (const b of $("quick").children) b.onclick = () => {
    if (b.dataset.mode === "bio" && mode() === "bio") { $("biolevel").value = bioLayer() === "biomes" ? "ecoregions" : "biomes"; return $("biolevel").onchange(); }
    if (b.dataset.mode === "bio" && bioLayer() === "realms") $("biolevel").value = "biomes";
    $("mode").value = b.dataset.mode; $("mode").onchange();
  };
  for (const b of toggles()) b.onclick = () => { const v = !layersOf(b).every(on); for (const k of layersOf(b)) document.querySelector(`[data-layer="${k}"]`).checked = v; togglesShown(); wanted(); draw(); };
  $("mode").onchange = () => { try { localStorage.mode = $("mode").value; } catch (e) { } modeChanged(); };
  $("biolevel").onchange = () => { try { localStorage.biolevel = bioLayer(); } catch (e) { } quickShown(); legend(); renderGroups(); draw(); };
  try { if ($("biolevel").querySelector(`[value="${localStorage.biolevel}"]`)) $("biolevel").value = localStorage.biolevel; } catch (e) { }
  try { setDay(localStorage.histday || "1914-06-28"); } catch (e) { setDay("1914-06-28"); }
  $("year").oninput = () => { setDay(yearText(+$("year").value) + histDay().replace(/^-?\d+/, "")); draw(); };
  $("day").onchange = () => { setDay($("day").value); $("day").value = showDay(histDay()); draw(); };
  modeChanged(false);
  $("palette").onchange = () => { try { localStorage.palette = $("palette").value; } catch (e) { } draw(); };
  for (const c of document.querySelectorAll("[data-layer]")) c.onchange = () => { togglesShown(); wanted(); draw(); };
  addEventListener("resize", resized);
  new ResizeObserver(resized).observe(canvas);
  load();
}
