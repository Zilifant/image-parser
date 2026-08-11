# image-parser

Internal tool that takes scanned pages of printed illustrations and breaks them
apart: it detects each individual graphic element on a page (automatically, or
guided by outlines you draw) and exports every element as its own
transparent-background PNG.

Runs entirely locally: React + TypeScript (Vite) frontend, Python + FastAPI
backend, all input/output files on your machine.

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
2. Open a page and hit **Detect elements**. Tune *merge radius* if elements
   come out over-merged (lower) or fragmented (higher).
3. Fix up the results: draw with the **Polygon**/**Lasso** tools, drag vertex
   handles, **Merge**/**Split**/delete regions, untick regions you don't want.
4. **Export page** — transparent PNGs land in
   `data/projects/<project>/pages/<page>/exports/` and show up in the review
   strip. Choose *ink* alpha (soft, keeps halftones) or *binary* (hard edges).

Batch: from the project view, **Detect all** processes every page and
**Export all…** writes every enabled region of every page to a folder you pick,
named `<page>_<label>.png`.

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

## Layout

- `backend/app/cv/pipeline.py` — element detection (illumination-flattened
  threshold, stroke bridging, contour extraction)
- `backend/app/cv/matte.py` — alpha-matte generation for exports
- `backend/app/routers/` — REST API (`/api/...`)
- `frontend/src/pages/EditorPage.tsx` — page editor (canvas, tools, export)
- `data/` — project storage (gitignored); `page.json` per page is the source
  of truth for regions
