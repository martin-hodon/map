#!/usr/bin/env python3
"""THE OFFLINE PACKAGE: offline.json -- every file the map needs, and a version (a hash of their contents). The service
worker (sw.js) keeps exactly these in the browser; the page compares this version with its own copy's and offers the
update, and keys its prepared data (IndexedDB) by it.

    python3 build/offline.py          (after build/lite.py or a point layer changed; then commit and push)
"""
import glob, hashlib, json, os, subprocess, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# what the page loads: itself, its libraries (lib/: kept here so the map opens offline), the light line layers and the
# point layers, the flags (flags.js, data/flags.txt, their gallery flags.html) (sw.js itself is the browser's to keep
# -- but it is hashed, so a change to it is a new version)
PATTERNS = ["index.html", "lib/*.js", "data/lite/*.txt", "data/*.csv", "flags.js", "flags.html", "data/flags.txt"]


def main():
    files = sorted({os.path.relpath(p, ROOT) for pat in PATTERNS for p in glob.glob(os.path.join(ROOT, pat))})
    # every file of the package must be ONLINE: one git ignores is never pushed, the site answers 404 and every update
    # fails on it (the language trainer's engine/listen.json did); one not yet added is a reminder before pushing
    ignored = subprocess.run(["git", "-C", ROOT, "check-ignore", "--no-index", *files], capture_output=True, text=True).stdout.split()
    if ignored: raise SystemExit("offline.json: these are in the package but git ignores them -- fix .gitignore: " + ", ".join(ignored))
    tracked = set(subprocess.run(["git", "-C", ROOT, "ls-files"], capture_output=True, text=True).stdout.split())
    new = [f for f in files if f not in tracked]
    if new: print("offline.json: not in git yet -- `git add` them before pushing, or every update fails on them: " + ", ".join(new))
    h = hashlib.sha1()
    for f in files + ["sw.js"]:
        h.update(f.encode()); h.update(open(os.path.join(ROOT, f), "rb").read())
    out = {"version": h.hexdigest()[:10], "made": time.strftime("%Y-%m-%d %H:%M"), "files": files + ["offline.json"]}
    open(os.path.join(ROOT, "offline.json"), "w", encoding="utf-8").write(json.dumps(out, indent=1) + "\n")
    size = sum(os.path.getsize(os.path.join(ROOT, f)) for f in files)
    print(f"offline.json: version {out['version']}, {len(files)} files, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
