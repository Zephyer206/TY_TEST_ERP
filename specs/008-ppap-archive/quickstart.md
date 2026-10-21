# PPAP acceptance

## Preview runtime

- Windows: `.venv\Scripts\python.exe scripts\setup_ppap_preview.py` stages a hash-verified local LibreOffice runtime without system installation. `--check` verifies it.
- Configure `PPAP_SOFFICE` to use a separately installed executable. `PPAP_STORAGE_ROOT` optionally changes private storage; public upload/static/frontend directories are rejected. Both settings may use the existing backend settings file or process environment.
- Back up PostgreSQL and `backend/private/ppap` (or the configured private root) together. File versions and submission snapshots depend on immutable originals.
- The PDF.js 5.6.205 browser assets and license are vendored under frontend/public/vendor/pdfjs and served locally.

## Small-host build

On this 4GB acceptance host, check PPAP types using `vue-tsc --noEmit -p frontend/tsconfig.ppap.json`. Full-project type checking is a separate check.

For packaging with bounded parallelism, set `GOMAXPROCS=1`, `GOMEMLIMIT=32MiB`, then run `node --max-old-space-size=736 --max-semi-space-size=1 --no-concurrent-marking --no-concurrent-sweeping scripts/build_frontend_low_memory.mjs`. This packages the entire frontend, serves local PDF assets, and disables minification for lower peak memory. Standard `npm run build` remains unchanged.

## Acceptance steps

1. Run targeted pytest tests for authorization, scope, concurrency, snapshots and content validation.
2. Apply additive Alembic migration; verify six new tables and current revision without outputting credentials.
3. Build frontend; run scripts/check_api_usage.ps1 and report existing debt separately.
4. Run app through existing cloud launcher. In a controllable browser open `/ppap`, record the browser session.
5. Quality: create archive with multiple valid company/customer links; root+two nested folders; upload PDF and two-sheet Excel with merged cells and image; open both previews.
6. Submit round 1, update original working filename version; view round 1 and verify old bytes; record temporary approval with deadline/conditions/evidence; submit round 2 and verify separate result.
7. Switch companies and reload; ensure scope is retained. Read-only identity: read/preview succeed, every write and original download forbidden.
8. View at phone width and desktop; verify breadcrumb/tree, dialogs, errors, no whole-page overflow, keyboard controls and company switch.

Implementation completion and browser acceptance completion must be reported separately. User's actual complex production workbooks remain subject to visual verification when provided; generated representative files are explicitly identified as test samples.
