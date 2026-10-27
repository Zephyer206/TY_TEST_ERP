# QR foundation, pool, print, binding and workspace acceptance

Run from the repository root with the project's Python environment:

```powershell
$env:PYTHONPATH = 'backend'
& backend/.venv/Scripts/python.exe -m pytest backend/tests/qr/ -q --tb=short
```

The existing backend test dependencies and `requirements.txt` in this directory
are required. The project Python includes the Windows timezone database; the
machine-wide Python installation may not have the same dependencies.

The fixture uses connection settings internally, creates a random `qrtmp_*`
database, verifies its name before DDL/DML, and checks the original OID before
dropping only that database. It never upgrades the business database. If the
connection lacks CREATE DATABASE permission, acceptance fails explicitly instead
of falling back to application data. No connection URLs are emitted or saved.

The service fixture can retry acquiring its async connection up to three times,
before it opens a transaction. Once a connection is acquired, it does not retry
DDL, DML, service operations, commits or any request whose result is uncertain.
This fixture behavior is not a business-operation replay policy. Its temporary
sync engine keeps one pre-pinged connection; it does not change the application's
production connection pool.

The actual self-contained Alembic revision runs through Alembic Operations against
synthetic legacy prerequisite tables, native or historic varchar scan columns,
and an existing legacy QR row. Tests compare the resulting schema to the ORM and
exercise upgrade, downgrade, re-upgrade, transaction abort, constraints, identity
protection and append-only records. New audit rows also prevent downgrade.

The service suites also test durable idempotency and safe rollback, department /
level / capability / owner authorization, live production contexts, 500 unique
pool identities, one-time binding with real concurrent sessions, print issuance
versus confirmation, stable reprint, actual authenticated ASGI routes, persisted
order selection without invented configuration, live actor/capability display,
metadata versions, allowed later route steps, immutable identities and rollback.
Material regression covers inbound/IQC/repeated splits, parent/sibling queries,
positive and invalid consumption, old-date reprint, and operator audit. The
material catalogue query eagerly loads `Material.supplier`, so the async response
can return `supplier_name` without lazy database IO during serialization.
`include_inactive` defaults to `false`; historical material lookup explicitly uses
`include_inactive=true` without changing the active catalogue default. The
catalogue regression asserts both scopes and supplier names through real ASGI
responses.

Latest full-run evidence is `runtime/qr-trace-full.xml` (229 passed).
`runtime/qr-trace-final.xml` has 22 passing trace/API cases, including two new
lineage/history regressions; `runtime/qr-trace-compat-final.xml` has three passing
overlapping quantity/HTTP/handoff cases after preserving the legacy idempotency
digest for requests that omit material_batch_id. Merge by classname/name,
taking the later result: 231 unique passing cases. Earlier phase3/phase4 reports
remain historical evidence; do not add overlapping run totals.

`test_order_configuration.py` covers atomic complete configuration, main/paired
products, explicit machine targets, immutable published routes and server-derived
conversion preauthorization. `test_production.py` covers ticket ownership/expiry,
independent machine contexts, explicit order selection, overwrite quantities,
stale versions, completion intent/differences, supervisor correction, demand locks,
allocation conflicts and historical routes. `test_production_api.py` exercises the
actual authenticated HTTP schemas/routes. The fixture includes the legacy
`Inventory` table because `Part.inventory_records` uses select-in loading; tests
do not weaken the application relationship or touch business inventory.

`test_process_trace.py` and `test_process_trace_api.py` cover next-step-only
handoff after completed machine production, snapshot quantities, stable identity,
one output source, material ancestry, null legacy metadata, cycles/broken links,
source/target pause guards, stale versions, cross-user/order rejection, rollback,
concurrent handoff, pagination and historical correction after downstream entry.
The optional material source is immutable after the first quantity record;
recording its association does not consume raw-material weight.

For real Vue page browser acceptance, run:

```powershell
& backend/.venv/Scripts/python.exe -X utf8 scripts/verification/serve_qr_ui_acceptance.py
```

For the production page, append `--production-fixture` to pre-issue two synthetic
labels with the actual generation service. Without this flag, the generic
material/pool diagnostic keeps its empty product-pool baseline.

Use `--trace-fixture` for the three-step CUT/FINISH/PACK route and
TRACE-CHILD/TRACE-MOTHER material ancestry; it also issues two synthetic labels.
The independent trace page is `/product-box-trace`; bootstrap with
`/acceptance/101?path=/product-box-trace` or 105 for the other order owner.

Use a separate Vite on port 18124 with process-local
`VITE_API_BASE_URL=/api/v1`. The latest UI server listens only on
`http://127.0.0.1:18125`. Bootstrap the actual router and pages with
`/acceptance/102?path=/product-box-qr` (production supervisor),
`/acceptance/103?path=/product-box-qr` (warehouse), or
`/acceptance/102?path=/material-qr` (material page). The server permits only its
listed synthetic identities and those pages plus `/product-box-production` and `/product-box-trace`.
Use `/acceptance/101?path=/product-box-production` for the worker, 102 for the
supervisor, 104 for order 401's owner, and 105 for the other order's owner.
The browser receives a
synthetic JWT in memory; never print or save the bootstrap page source. Its
authentication setting is process-local and does not change real user grants or
the normal application setting. Do not mount this server in production.

POST `http://127.0.0.1:18125/acceptance-stop` for normal shutdown. The factory
checks the creation name and original OID, drops only its owned disposable
database, then marks `runtime/qr-ui-owned.json` as `cleaned`. Stop only the Vite
process verified to belong to this diagnostic afterward.

If the UI process is interrupted, `scripts/verification/cleanup_owned_qr_ui.py`
can recover cleanup from `runtime/qr-ui-owned.json`. It requires a valid
`qrtmp_<32 hex>` name, the original creation OID, the exact synthetic UI purpose,
and a name different from the configured business database. It refuses a changed
OID or any active database sessions; stop the owned UI server first. Before
dropping, it preserves sanitized synthetic counts in
`runtime/qr-ui-recovered-summary.json`, then rechecks the original OID. An already
absent database is marked cleaned. A prefix alone, a matching current database
name, or guessed ownership is never permission to delete another residual test
database. The journal contains no connection string, credentials or JWT.

The earlier `scripts/verification/serve_qr_client_acceptance.py` is a loopback-only
wrapper diagnostic using this same disposable database factory. With Vite on
18124 and its process-local `VITE_API_BASE_URL=/api/v1`, open
`http://127.0.0.1:18123/acceptance` in a controllable browser to test the actual
frontend domain wrapper. Synthetic JWTs live only in memory; never print or save
the page source or mount this diagnostic in production. POST to
`http://127.0.0.1:18123/acceptance/stop` for normal shutdown and owned DB cleanup;
stop only the matching diagnostic Vite process afterward. The normal application
authentication bypass and real user grants are not changed by this workflow.

Automated suites and the earlier wrapper diagnostic do not substitute for real
browser checks of the Vue pages. UI acceptance is recorded separately from test
results. Neither workflow prints physical labels or authorizes real users, and
the fixtures do not replay unrelated historical migrations. Production quantities
and process advancement/trace are implemented; split boxes are now implemented; notifications and
conversions remain future suites.
Database defaults and business writes should use the database clock consistently;
client clocks can differ by milliseconds and are not the audit authority.


## Product box splits (2026-10-27)

`test_split.py` has 31 PostgreSQL service cases and `test_split_api.py` has 10
actual authenticated HTTP cases. They cover repeated same-order partitions,
positive/zero balances, mixed order/stock uses, scoped cross-order transfers,
strict input, immutable metadata identity, replay/rollback, downstream guards,
cleared completion intents, current later-process recount and two concurrency
races (one parent balance; separate receiving states sharing target demand).
The related production/process/API run passed 84 cases. Full-suite results are
recorded separately in the phase6 evidence; overlapping test counts are not added.

Run `scripts/verification/serve_qr_ui_acceptance.py --split-fixture` against a
dedicated Vite on 18124 to seed a produced 100-piece parent, a compatible target
order and eight unused child labels. Browser actions perform the actual splits.
`verify_qr_phase6.py --snapshot` verifies the journalled original OID and uses
an explicitly read-only transaction. It preserves physical/use conservation,
origin allocation links, source snapshots, material and continued-process facts.
Normal server shutdown cleans only this run's database; no real grants, tokens
or business migrations are stored by this workflow.
