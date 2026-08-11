# image-parser

Internal tool that bulk-processes scanned/collage artwork: it detects each
individual design on a page (automatically, or guided by outlines you draw),
cleans it, and exports every design as its own transparent-background PNG —
**white-on-transparency by default**, with original-color and pure-black modes
too.

Runs entirely locally: React + TypeScript (Vite) frontend, Python + FastAPI
backend, all input/output files on your machine. See `PLAN.md` for the full
design; the project brief it implements is a deterministic (non-generative)
OpenCV pipeline with a review GUI.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Node 18+.

```sh
make setup     # installs backend (uv sync) and frontend (npm install) deps
```

## Run

```sh
make dev       # starts backend (:8765) + frontend (:5173), opens the browser
```

Then, in the app:

1. Create a project, add scans — upload files or point at a local folder.
2. Open a page, optionally apply a **processing profile**
   (`clean-photocopies`, `yellowed-magazines`, `low-contrast-scans`,
   `dense-collages`, or save your own), and hit **Detect elements**. Tune
   *merge radius* if designs come out over-merged (lower) or fragmented
   (higher).
3. Review: suspicious regions are auto-**flagged** (dashed red) — press
   **N** to jump to the next flagged region, fix it (polygon/lasso tools,
   vertex handles, **Merge**/**Split**/delete), then press **A** to approve.
4. **Export page** — transparent PNGs land in
   `data/projects/<project>/pages/<page>/exports/` and show up in the review
   strip. Choose *ink* alpha (soft, keeps halftones) or *binary* (hard
   edges), and white/original/black foreground. Every export runs automated
   **quality checks** (alpha present, non-empty, not cut off at the crop
   edge, correct foreground color); failures are flagged back into review
   with a red border in the strip.
5. **Clean full page** exports the whole page as one white-on-transparent
   PNG; **Contact sheet ↗** opens a numbered grid of all exported crops.

Batch: from the project view, **Detect all** processes every page and
**Export all…** writes every enabled region of every page to a folder you pick,
named `<page>_<label>.png`.

### Headless CLI

The processing engine also runs without the GUI:

```sh
cd backend
uv run python -m app.cli ~/scans/ -o ~/out --profile dense-collages --clean-page
```

## Optional: SVG vectorization (Potrace)

`brew install potrace` and restart — an **Export SVG** button appears in the
editor for the selected region (the PNG stays alongside the SVG).

## Optional: Segment Anything (SAM)

Classical OpenCV detection handles clean, well-separated elements. For touching
or overlapping elements, enable the optional MobileSAM tools:

```sh
cd backend && uv sync --extra sam   # installs torch + mobile-sam
make download-sam                   # fetches the ~40MB checkpoint
```

Restart the app; **SAM point** (click an element) and **SAM box** (drag around
one) appear in the editor toolbar. Without the checkpoint the app runs fine and
simply hides those tools.

## Tests

```sh
make test      # pytest: CV pipeline against assets/raw-images/eyes-11.png + API flow
```

Browser smoke test (with `make dev` running):

```sh
npm install --no-save playwright-core   # once, anywhere on NODE's path
node scripts/e2e.mjs                    # set CHROMIUM=<path> if Chrome isn't in the default macOS location
```

## Layout

- `backend/app/cv/pipeline.py` — element detection (illumination-flattened
  threshold, stroke bridging, contour extraction)
- `backend/app/cv/matte.py` — alpha-matte generation for exports
- `backend/app/routers/` — REST API (`/api/...`)
- `frontend/src/pages/EditorPage.tsx` — page editor (canvas, tools, export)
- `data/` — project storage (gitignored); `page.json` per page is the source
  of truth for regions
