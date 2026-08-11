# Image Parser — Implementation Plan

## Context

The user wants an internal-use app that takes scanned pages of printed illustrations (e.g., `assets/raw-images/eyes-11.png` — a 1174×1554 vintage page densely packed with ~40+ individual eye engravings on off-white paper) and "parses" them: detecting each individual graphic element and exporting it as its own transparent-background PNG. Processing works fully automatically, or with manual guidance — at minimum the user drawing outlines (polygon/lasso) around elements. Single images and batches (folders) are both supported.

The originating ChatGPT conversation could not be fetched (chatgpt.com is blocked by this environment's network proxy), so requirements were confirmed directly with the user:

- **Architecture**: React + TypeScript (Vite) frontend, Python + FastAPI backend.
- **Local web app on macOS**: one script starts both servers and opens the browser. Single user, no auth, all files local.
- **Export v1**: transparent PNG per element (alpha-matted crop). No SVG/PSD.
- **Segmentation**: classical OpenCV pipeline by default; Segment Anything (MobileSAM) as an *optional* mode — app fully works without the model.
- **No macOS app integrations in v1.**

All work goes on branch `claude/image-parsing-export-app-3itzt6`, committed and pushed per milestone. The repo's empty `PLAN.md` will be filled with a copy of this plan in M1.

## Repo layout & tooling

```
image-parser/
├── Makefile                  # make setup / dev / test / download-sam
├── scripts/dev.sh            # starts backend + frontend, opens browser
├── assets/raw-images/        # sample inputs (existing)
├── data/                     # project storage root (gitignored)
├── backend/
│   ├── pyproject.toml        # uv-managed; optional-dependency group "sam"
│   ├── app/
│   │   ├── main.py, config.py, schemas.py, store.py, jobs.py
│   │   ├── routers/  projects.py, pages.py, regions.py, export.py, jobs.py, fs.py, sam.py
│   │   └── cv/       pipeline.py, matte.py, sam_backend.py
│   └── tests/        test_pipeline.py, test_api.py
└── frontend/
    └── src/
        ├── api/client.ts, api/types.ts       # typed fetch wrappers mirroring schemas.py
        ├── state/editorStore.ts              # zustand (UI state only)
        ├── pages/LibraryPage.tsx, pages/EditorPage.tsx
        └── components/
            ├── canvas/PageCanvas.tsx, RegionOverlay.tsx, PolygonTool.tsx
            └── RegionList.tsx, Toolbar.tsx, ExportPanel.tsx, DetectParamsPanel.tsx, FolderPicker.tsx
```

- **Python**: managed with **uv** (venv + lockfile in one tool; `uv sync --extra sam` cleanly handles the optional SAM group). Core deps: `fastapi`, `uvicorn[standard]`, `opencv-python-headless`, `numpy`, `pillow`, `python-multipart`; dev: `pytest`, `httpx`. Optional `sam` extra: `torch`, `mobile-sam`.
- **Frontend**: `react`, `react-dom`, `typescript`, `vite`, `react-router-dom`, `@tanstack/react-query`, `zustand`.
- **Canvas**: plain `<img>` + **SVG overlay** (no react-konva). Regions are polygons; SVG gives free hit-testing, CSS hover/selection styling, crisp rendering at any zoom. Zoom/pan is one CSS transform on a container holding both the image and the SVG (shared image-pixel coordinate space).

## Backend design

**Storage — filesystem + JSON sidecars (no sqlite).** Under `DATA_DIR` (default `./data`, env-overridable):

```
data/projects/<project_id>/project.json
data/projects/<project_id>/pages/<page_id>/
    original.png  thumb.jpg  page.json     # page.json holds the full region list — it IS the database
    masks/<region_id>.png                  # only for SAM/merged regions where polygon isn't authoritative
    exports/<region_id>.png
```

Atomic JSON writes (temp file + `os.replace`) in `store.py`.

**Regions over the wire — polygons** (`[[x,y],...]` in image-pixel coords, from `cv2.findContours` + `approxPolyDP`). Directly renderable/editable as SVG; the server regenerates the fine alpha matte from the original image within the polygon at export time, so pixel-perfect wire masks aren't needed. Region shape:

```json
{"id": "r_a3f9", "bbox": [x,y,w,h], "polygon": [[x,y],...],
 "source": "auto|manual|sam|merge", "confidence": 0.92,
 "enabled": true, "label": "eye-03", "mask_url": null}
```

**CV pipeline** (`cv/pipeline.py`, `detect_regions(bgr, params)`):
1. Flatten RGBA onto white → grayscale.
2. Illumination flattening: `bg = morphologyEx(gray, MORPH_CLOSE, ellipse(51,51))`; `norm = divide(gray, bg, scale=255)` — kills paper tint and staining.
3. `adaptiveThreshold(norm, ..., THRESH_BINARY_INV, blockSize=51, C=12)` (params exposed; Otsu fallback mode).
4. Despeckle: `MORPH_OPEN` 3×3.
5. Stroke bridging: `MORPH_CLOSE` 5×5 ×2 + dilate by `merge_radius` (default ~6px, auto-scaled to image width) — the key knob joining an engraving's hatching into one blob.
6. `findContours(RETR_EXTERNAL)` on the dilated mask.
7. Filter: `min_area` (default 0.02% of page), drop border artifacts, cap `max_area` at 90% of page.
8. Merge-nearby: inflate bboxes by `merge_radius`, union-find overlaps, merge grouped contours.
9. Emit tight bbox + polygon from the *undilated* mask, plus a solidity/fill-based confidence heuristic.

Expected on the sample: the Arabic-labeled central diagram and bottom banner come out as single large regions (correct — user splits or lassos subparts); touching elements (arrow piercing the big eye) merge — that's the manual/SAM use case.

**Alpha matte** (`cv/matte.py`): crop bbox+pad from the original, rasterize polygon (or load stored mask), locally re-threshold the illumination-normalized crop inside the mask, then alpha styles: `"ink"` (default — `alpha = 255 − norm`, zeroed outside mask; halftone dots get partial transparency) or `"binary"` (feathered thresholded mask). RGB = original crop colors, optional `"pure_black"` mode. Save RGBA PNG via Pillow.

**Jobs** (`jobs.py`): in-process dict registry + `ThreadPoolExecutor(max_workers=1)`; batch endpoints return `{job_id}`; frontend polls `GET /api/jobs/{id}` (~500ms). No celery/redis; jobs die with the process — acceptable.

**SAM** (`cv/sam_backend.py`): `is_available()` checks import + checkpoint at `config.SAM_CHECKPOINT`; `GET /api/sam/status` lets the UI hide the mode. Lazy singleton predictor, per-page embedding cache (LRU 2). Predictions become normal regions (`source:"sam"`) with a stored mask PNG + outer-contour polygon. MobileSAM (~40MB, fast on CPU/MPS); `make download-sam`.

## API contract (base `/api`)

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/projects` | list / create |
| GET/DELETE | `/projects/{pid}` | detail incl. page summaries / delete |
| GET | `/fs/list?path=/abs/dir` | folder-picker listing `{entries:[{name,path,is_dir,is_image}]}` |
| POST | `/projects/{pid}/pages` | multipart upload (1..n) → `[Page]` |
| POST | `/projects/{pid}/pages/from-paths` | `{paths:[...]}` or `{dir:"/abs"}` → `[Page]` |
| GET | `.../pages/{pgid}` | page + `regions:[Region]` + `detect_params` |
| GET | `.../pages/{pgid}/image` \| `/thumb` | image bytes |
| POST | `.../pages/{pgid}/detect` | `{params?}` → regions (replaces `auto`, keeps manual/sam) |
| POST | `.../pages/{pgid}/regions` | `{polygon}` → manual Region |
| PATCH/DELETE | `.../regions/{rid}` | `{polygon?,enabled?,label?}` / delete |
| POST | `.../regions/merge` | `{region_ids}` → merged Region |
| POST | `.../regions/{rid}/split` | re-detect inside region with smaller merge_radius |
| POST | `.../regions/{rid}/export` | `{style?,rgb?,padding?}` → `{export_url}` |
| POST | `.../pages/{pgid}/export` | enabled regions → `{exports:[...]}` |
| POST | `/projects/{pid}/detect-all` \| `/export-all` | → `{job_id}` (export-all takes `out_dir?`) |
| GET | `/jobs/{job_id}` | `{status, progress:{done,total}, error?}` |
| GET | `/sam/status` | `{available, model?}` |
| POST | `.../pages/{pgid}/sam/predict` | `{points?|box?}` → Region |

## Frontend design

- **LibraryPage** (`/`, `/projects/:pid`): project list/create; page thumbnail grid with status badges (no regions / detected N / exported); Add images (multi-file upload), Add folder (FolderPicker → `fs/list` → `from-paths`); Detect-all / Export-all with job progress bars.
- **EditorPage** (`/projects/:pid/pages/:pgid`):
  - **PageCanvas**: wheel zoom-to-cursor, space/drag pan via one CSS transform.
  - **RegionOverlay**: one `<polygon>` per region, tinted by enabled/selected/hover state; click select, shift multi-select, Delete key; selected region shows draggable vertex handles (PATCH on drag-end, optimistic update).
  - **Toolbar**: Select / Draw polygon / Freehand lasso / (SAM point & box when available); Detect + DetectParamsPanel (min-area, merge-radius, threshold sliders → re-run); Merge / Split selected.
  - **PolygonTool**: polygon = click vertices, Enter/double-click closes; lasso = pointer-drag sampling every ~4px, client-side Douglas-Peucker simplify before POST.
  - **RegionList** sidebar: sort by confidence/area, hover-sync, rename labels.
  - **ExportPanel**: matte style, RGB mode, padding; Export selected/page; then a checkerboard thumbnail strip of resulting PNGs — the review loop (eyeball → fix outlines → re-export overwrites).
- **State**: TanStack Query owns all server state (incl. job polling via `refetchInterval`); zustand `editorStore` owns UI-only state (tool, transform, selection, in-progress polygon, params draft).

## Dev/run ergonomics

- `make dev` → `scripts/dev.sh`: `uv run uvicorn app.main:app --reload --port 8765` (bound to 127.0.0.1) + `npm run dev` (vite :5173), trap kills both on Ctrl-C, waits for `/api/health`, then `open http://localhost:5173`.
- No CORS: vite proxies `/api` → `:8765`.
- Browser never touches the filesystem: FolderPicker browses via `GET /api/fs/list` (rooted at `$HOME`, absolute paths only); backend does all file I/O. Fine for a trusted local single-user tool.
- `make setup` = `uv sync` + `npm install`; `make test` = `uv run pytest`.

## Milestones

**M1 — Skeleton + auto-detect + export (single image).** Scaffolding, `make dev`, project/page upload, detect endpoint + CV pipeline, region overlay (view/select/toggle/delete), page export with ink matte, pipeline tests. Copy plan into repo `PLAN.md`.
*Verify:* `make dev`; upload `eyes-11.png`; Detect → ≥25 regions covering individual eyes, none spanning the whole page; Export page → open `exports/` and confirm transparent-background crops with clean alpha. `make test` green.

**M2 — Manual tools + region editing.** Polygon + lasso, vertex editing, merge/split, params panel with re-run, export panel + review strip, labels.
*Verify:* lasso the stylus that crosses other elements and export it; Split the merged arrow+big-eye blob; merge-radius slider changes region count live.

**M3 — Batch.** Folder ingestion + FolderPicker, detect-all/export-all jobs with progress, status badges, batch `out_dir`.
*Verify:* folder of 3 copies of the sample → Detect all (0/3→3/3) → Export all to a chosen out_dir → PNGs named `<page>_<label>.png` land there.

**M4 — Optional SAM.** `make download-sam`, sam_backend + status endpoint, SAM tools appear only when available, embedding cache.
*Verify:* without checkpoint the app runs with SAM UI hidden; with it, click a pupil that classical CV merged with a neighbor → clean single-eye region + export.

## Testing

- `test_pipeline.py` against the sample asset: detects 25–120 regions, all bboxes in-bounds, none >90% of page; median region area 0.05–10% of page; exported matte is RGBA with transparent corners and >5% opaque pixels; larger `merge_radius` ⇒ fewer-or-equal regions.
- `test_api.py` (TestClient, `tmp_path` DATA_DIR): create project → upload → detect → PATCH polygon → export page → export file exists and is a valid PNG; one detect-all job test.
- Frontend: no unit tests in v1; manual verification per milestone checklists.

## Critical files

- `backend/app/cv/pipeline.py` — detection pipeline (technical core)
- `backend/app/cv/matte.py` — alpha matte / export quality
- `backend/app/routers/pages.py` — ingestion + detect endpoints
- `frontend/src/pages/EditorPage.tsx` — editor shell
- `frontend/src/components/canvas/RegionOverlay.tsx` — main interaction surface
