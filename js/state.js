// state.js -- what every module shares: the canvas, the DOM helper, the view (projection, rotation, zoom), the data loaded, the selection -- the mutable parts in S
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { PALETTES } from "./style.js";

// S: the mutable shared state -- every top-level `let` the script reassigned somewhere, one object so that every module
// reads and writes the same value (an imported binding cannot be assigned)
export const S = {};
// A look at data/: every layer in any d3 projection. The layers are longitude/latitude with edges meant as the
// shortest way over the globe, so each projection draws them as they are -- nothing here is pre-projected.
// Speed: each layer's pieces sit in an R-tree by their bounding boxes and only the ones in view are drawn; every line
// layer is three files (data/, data/small, data/xsmall: build/small.py) and each view uses the coarsest still about as
// fine as a pixel; while the map moves it is drawn from a coarser one where that is still within a few pixels, without
// labels, a frame at a time, and whole once it stops.
// Memory: a layer's points sit in one typed array and its rows are numbers into it (THE LINES, below); GeoJSON is made
// only for what asks for it, a click or a selection, and a layer not in use for a few minutes is let go (RELEASE).
export const $ = (id) => document.getElementById(id);
export const canvas = $("map"), ctx = canvas.getContext("2d");
export const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
export const R_KM = 6371;
// the view's centre never right on the equator: the globe's edge then runs through both poles, along Antarctica's
// edge at -90°, and its clip takes Antarctica (the land, the realm) for all the sphere round it
// (nor right over a pole, where a drag ends: every line through it is then on the same meridian and the clip paints the same way)
export const tilt = (r) => Math.abs(r[1]) < 1e-3 ? [r[0], -1e-3, r[2]] : Math.abs(r[1]) > 90 - 1e-3 ? [r[0], Math.sign(r[1]) * (90 - 1e-3), r[2]] : r;
export let trees = {}, points = {}, index = [];
S.rotate = [-10, 0, 0]; S.zoom = 1; S.src = null; S.sel = null;
// (S.W: set later)
// (S.H: set later)
// (S.dpr: set later)
// (S.proj: set later)
// (S.path: set later)
export const on = (k) => document.querySelector(`[data-layer="${k}"]`).checked;
export const HOW = matchMedia("(pointer: coarse)").matches ? "drag to turn, pinch to zoom, tap to see what is there" : "drag to turn, wheel to zoom, click to see what is there";   // (a phone's fingers, or a mouse)
export const GAME_ZOOM = 25;   // (the game flies less close, and never closer: Vatican City a dot among Rome and the hills, not the screen)
export const MAX_ZOOM = 300;   // (about 100 m a pixel on a 1400 px screen: the coast is kept to 100 m, lines to 0.5 km)
export const dark = () => matchMedia("(prefers-color-scheme: dark)").matches;
export const fmt = (n) => Math.round(n).toLocaleString("en");
export const fmtPop = (n) => n >= 1e9 ? `${(n / 1e9).toFixed(2).replace(/\.?0+$/, "")} billion` : n >= 1e6 ? `${(n / 1e6).toFixed(1).replace(/\.0$/, "")} million` : `${Math.round(n / 1e3)}k`;   // (the data holds 2 digits)

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  $("hint").textContent = HOW;
  try { if (PALETTES[localStorage.palette] !== undefined) $("palette").value = localStorage.palette; else if (dark()) $("palette").value = "dark muted"; } catch (e) { }
}
