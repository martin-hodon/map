// scale.js -- the scale bar, bottom left: a round length (1, 2 or 5 times a power of ten, km or m) 50-120 px long, as
// measured on the ground across the middle of the view (every projection here stretches somewhere, the globe's edge most:
// the middle is where one looks); none where the middle is off the earth (the globe's sky) or the whole world is in view
// and a length means little (over 2,000 km for 100 px)
import { S } from "./state.js";

const R = 6371.0088;                                                  // (km, the mean radius)
const hav = (a, b) => {
  const r = Math.PI / 180, dl = (b[0] - a[0]) * r, dp = (b[1] - a[1]) * r;
  const h = Math.sin(dp / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dl / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
};
const nice = (km) => { const p = 10 ** Math.floor(Math.log10(km)), f = km / p; return (f >= 5 ? 5 : f >= 2 ? 2 : 1) * p; };
const text = (km) => km >= 1 ? `${km.toLocaleString("en")} km` : `${Math.round(km * 1000)} m`;

let box, bar, lab, last = "";
export function drawScale() {
  if (!S.proj) return;
  if (!box) {
    box = document.createElement("div"); box.id = "scale"; box.setAttribute("aria-hidden", "true");
    bar = document.createElement("i"); lab = document.createElement("span"); box.append(lab, bar); document.body.append(box);
  }
  const x = S.W / 2, y = S.H / 2, a = S.proj.invert([x - 50, y]), b = S.proj.invert([x + 50, y]);
  const ok = a && b && [...a, ...b].every(isFinite) && S.proj(a) && Math.abs(S.proj(a)[0] - (x - 50)) < 1 && Math.abs(S.proj(b)[0] - (x + 50)) < 1;
  const per = ok ? hav(a, b) / 100 : 0;                               // (km a pixel there)
  if (!per || per * 100 > 2000) { if (last) { box.hidden = true; last = ""; } return; }
  const km = nice(per * 120), px = Math.round(km / per), key = km + ":" + px;
  if (key === last) return;
  last = key; box.hidden = false; lab.textContent = text(km); bar.style.width = px + "px";
}
