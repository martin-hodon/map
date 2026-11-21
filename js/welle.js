// welle.js -- the NOTES that name a thing: ../welle's data/back.json (its build/links.py writes it from the same matches
// welle shows the map and the atlas with), read once when first needed. Without welle beside the app (another server,
// a copy of the app alone) there are none. (The same file in map/js, atlas/js and multiverse: each app draws them its way.)
let back = null;                                                    // (a promise of back.json, once it has come)

// the lines naming it: kind "place" (by its wikidata or iso id, else `name|cat`, the map's name and its cat), "body" (by
// the atlas key, its side left out), "model" (the game's asset path) -> { lines: [{ text, file, href }], total }: the
// first few lines (12), and how many there are in all. (key: one, or a list of them tried in turn -- the first found)
export function welleLines(kind, key) {
  // (a failed read -- offline, no welle -- is not kept: the next thing asked for tries again)
  back ??= fetch("../welle/data/back.json").then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .catch(() => { back = null; return {}; });
  return back.then((b) => {
    const found = [key].flat().map((k) => b[kind]?.[k]).find(Boolean);
    const [lines, total] = found ?? [[], 0];
    return { total, lines: lines.map(([file, li, text]) => ({
      text, file: file.split("/").pop().replace(/_/g, " "),
      href: `../welle/index.html#/notes/${file.split("/").map(encodeURIComponent).join("/")}?l=${li}`,
    })) };
  });
}
