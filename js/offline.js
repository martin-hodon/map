// offline.js -- the offline copy (sw.js, offline.json): registering, checking for a newer version, updating
// (split out of index.html's one script, 2026-11-09: split.js in the session's scratchpad; the names are the script's own)
import { $ } from "./state.js";

// ---- loading, and the index of names -------------------------------------------------------------------------------
// ---- the offline copy -------------------------------------------------------------------------------------
// THE OFFLINE COPY (sw.js; offline.json -- build/offline.py -- lists the files and their version): on a real site the
// service worker keeps every file the map loads, so it opens with no network and downloads nothing again. It does not
// update on its own: once a visit the page asks for the version online, and a newer one shows a line at the top with
// its Update -- the version kept and a check are also at the panel's foot. Updating replaces only the kept files; the
// groups, the mode and the other settings stay.
export const OFFLINE = "map-";
export async function startOffline() {   // -> the version kept ("" while the first copy is being made, null with no worker)
  if (!/^https?:$/.test(location.protocol) || !("serviceWorker" in navigator) || !("caches" in self)) return null;
  try { await navigator.serviceWorker.register("sw.js"); } catch (e) { console.warn("map: no offline copy --", e); return null; }
  navigator.storage?.persist?.();   // (asks the browser not to clear the copy when space runs short)
  const keys = (await caches.keys()).filter((k) => k.startsWith(OFFLINE));
  return keys.length ? keys[keys.length - 1].slice(OFFLINE.length) : "";
}
export const onlineVersion = async () => { try { return (await (await fetch("offline.json?" + Date.now(), { cache: "no-store" })).json()).version; } catch { return null; } };
export async function updateOffline() {   // every file of the online version into its own cache; the old one dropped only once the new one is whole
  const manifest = await (await fetch("offline.json?" + Date.now(), { cache: "no-store" })).json();
  const name = OFFLINE + manifest.version, cache = await caches.open(name);
  try { await cache.addAll(manifest.files.map((f) => new Request(f, { cache: "reload" }))); }
  catch (e) { await caches.delete(name); throw e; }
  for (const k of await caches.keys()) if (k.startsWith(OFFLINE) && k !== name) await caches.delete(k);
  location.reload();
}
export function showVersion(kept) {
  if (kept === null) return;
  const here = kept ? `offline copy ${kept}` : "making the offline copy…";
  $("version-text").textContent = here; $("checkUpdate").hidden = false;
  const run = async (button) => {
    for (const b of [$("doUpdate"), $("noteUpdate")]) { b.disabled = true; b.textContent = "updating…"; }
    try { await updateOffline(); } catch (e) { for (const b of [$("doUpdate"), $("noteUpdate")]) { b.disabled = false; b.textContent = "update failed — try again" + (b === button && e?.message ? ` · ${e.message}` : ""); } }
  };
  const ask = async (quiet) => {
    $("checkUpdate").disabled = true;
    const online = await onlineVersion();
    $("checkUpdate").disabled = false;
    if (online && kept && online !== kept) {
      $("version-text").textContent = `${here} · new: ${online}`;
      Object.assign($("doUpdate"), { hidden: false, textContent: "update now", onclick: () => run($("doUpdate")) });
      $("update-text").textContent = `A new version of the map is ready (${online}) — your groups and settings stay.`;
      $("noteUpdate").onclick = () => run($("noteUpdate")); $("update-note").hidden = false;
    } else if (!quiet) $("version-text").textContent = `${here} · ${online === null ? "no network: nothing to check" : "the newest"}`;
  };
  $("checkUpdate").onclick = () => ask(false);
  if (kept) ask(true);
}

// the wiring that ran at the script's top level, in its order (main.js calls the modules' inits in section order)
export function init() {
  try { indexedDB.deleteDatabase("map"); } catch (e) { }   // (what was kept there once: reading the files is now as quick)
}
