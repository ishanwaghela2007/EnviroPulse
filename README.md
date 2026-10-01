# EnviroPulse — Real-Time Air & Water Quality Intelligence for Industrial Zones

HackConquest 2026 · Problem Statement 13 · working prototype

EnviroPulse gives an environmental officer one screen per industrial zone. It shows what is happening
(map and KPIs) and when it changed (trends). It says whether the change is unusual (anomaly detection) and
what the likely contributors are, **as an estimate, not proof**. It projects what may happen next (a forecast
with an uncertainty band) and what to do about it (threshold alerts with persistence, acknowledgement and
feedback).

Behind the screen, every number comes from one backend pipeline:

```
Collect → Unify → Detect → Explain → Predict → Alert → operator feedback
```

> **Honesty notice.** Zone boundaries are synthetic, the seven factories are fictional, and the air, water,
> factory and event feeds in the demo are a **SIMULATED DEMO STREAM**. The UI labels them as such everywhere.
> Real OpenAQ and India OGD connectors are implemented. They stay `OFFLINE` until you provide API keys, and
> they never fabricate data.

---

## Contents
1. [Quick start (Docker)](#1-quick-start-docker)
2. [Local development setup](#2-local-development-setup)
3. [The golden demo (5 minutes)](#3-the-golden-demo-5-minutes)
4. [How PS 13 is covered](#4-how-ps-13-is-covered)
5. [Architecture](#5-architecture)
6. [Tech stack](#6-tech-stack)
7. [Project structure](#7-project-structure)
8. [Data sources and the simulated-data policy](#8-data-sources-and-the-simulated-data-policy)
9. [Ingestion and validation](#9-ingestion-and-validation)
10. [Geo-time alignment and features](#10-geo-time-alignment-and-features)
11. [Anomaly detection](#11-anomaly-detection)
12. [Source attribution (estimate)](#12-source-attribution-estimate)
13. [Forecasting](#13-forecasting)
14. [Thresholds and alerts](#14-thresholds-and-alerts)
15. [Operator feedback loop](#15-operator-feedback-loop)
16. [Database](#16-database)
17. [API reference](#17-api-reference)
18. [Redis usage](#18-redis-usage)
19. [Background workers](#19-background-workers)
20. [Frontend](#20-frontend)
21. [Configuration (environment variables)](#21-configuration-environment-variables)
22. [Testing and results](#22-testing-and-results)
23. [Acceptance criteria evidence](#23-acceptance-criteria-evidence)
24. [Known limitations](#24-known-limitations)
25. [Troubleshooting](#25-troubleshooting)
26. [Deployment notes](#26-deployment-notes)

---

## 1. Quick start (Docker)

Requirements: Docker with Compose v2.

```bash
docker compose up --build
```

| What | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| API (OpenAPI docs) | http://localhost:8000/docs |
| API health | http://localhost:8000/api/v1/health |

The first start does four things in order:

1. Waits for PostgreSQL.
2. Applies the Alembic migrations.
3. Seeds about 14 days of simulated history through the real ingestion pipeline (roughly 40 s).
4. Starts the API with the background scheduler.

Later restarts **do not** reseed, so alert history and feedback are preserved.

Optional live air data: `OPENAQ_API_KEY=... OGD_API_KEY=... docker compose up --build`.

> Status: the compose file, both Dockerfiles and the container entrypoint were written and checked in the build
> environment. The entrypoint's wait → migrate → seed-once sequence was executed against a fresh, empty
> PostgreSQL/PostGIS database. **`docker compose up` itself could not be run there (no Docker available)**,
> so treat the first container build as untested.

## 2. Local development setup

Requirements: Python 3.12, Node 22, PostgreSQL 16 with PostGIS 3.4, Redis 7.

```bash
# 1. database (once)
createuser -P enviro                     # password: enviro (or change DATABASE_URL)
createdb -O enviro enviropulse
psql -d enviropulse -c "CREATE EXTENSION IF NOT EXISTS postgis;"   # needs a superuser

# 2. backend
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                     # adjust DATABASE_URL / REDIS_URL if needed
alembic upgrade head
python -m app.seed.seed_database         # ~40 s: 14 days of history + analytics
uvicorn app.main:app --reload --port 8000

# 3. frontend (new terminal)
cd frontend
npm ci
cp .env.example .env
npm run dev                              # http://localhost:5173
```

Useful commands:

| Command | Purpose |
|---|---|
| `python -m app.seed.reset_demo` | Truncate everything, clear Redis, reseed (replay the golden scenario) |
| `python -m app.seed.generate_demo_stream --ticks 12 --interval 3` | Play the golden scenario from the terminal |
| `python -m app.seed.generate_demo_stream --outage sim_air` / `--restore sim_air` | Simulate a feed outage / recovery |
| `python -m app.workers.runner` | Run the scheduler as a separate process |
| `python -m pytest` (in `backend/`) | Backend tests (needs a test database; see §22) |
| `npm test` / `npm run build` (in `frontend/`) | Frontend tests / production build |

## 3. The golden demo (5 minutes)

The dashboard opens on **Industrial Zone A**. A dark bar at the bottom, **SIMULATED DEMO STREAM**, drives the
scenario. Every click on **Advance one window** makes the backend ingest one new 15-minute window for all
zones. That window goes through validation, alignment, feature computation, anomaly detection, attribution,
alert evaluation and forecasting. The dashboard then refreshes because the backend's `data_version` changed.
Nothing in the UI is animated or scripted client-side.

| Window | What happens | Where to look |
|---|---|---|
| 1–3 | Normal readings | KPIs, trend |
| 4 | Apex Organics (fictional) raises production to about 88%. PM2.5 hasn't moved yet. | Map factory popup, trend (dashed factory line) |
| 5 | PM2.5 jumps to about 71 µg/m³, one window after the factory. **Anomaly** detected (≈3.7σ). First threshold breach, **no alert yet**. | Anomaly timeline (violet point), threshold table shows 1/3 |
| 6 | A construction event starts nearby. Second consecutive breach. | Trend (shaded event), threshold table 2/3 "awaiting persistence" |
| 7 | Third consecutive breach, so the **alert is created**. | Current alert card, pipeline rail "Alert" turns red |
| 8–10 | Breach continues. The **same alert is updated**, never duplicated. | Alert log (one row), alert history "Updated" |
| 11 | PM2.5 back within limits: recovery 1 of 2 | Alert history "Recovering" |
| 12 | Second clearly-normal window: the **episode resolves** | Alert status `resolved` |

What to show along the way:

- **Attribution.** Click the violet anomaly point, then open *Source attribution*. Apex Organics ranks #1 at
  lag t-1 (r ≈ 0.95–0.97), labelled **ESTIMATE**, with evidence text and the scatter caption *"Association
  only — not proof of causation."* The simulator injected exactly this relationship, and the analytics never
  see the simulator's parameters, so the method recovers it independently.
- **Forecast.** It shows the next 2 hours with a band, MAE/RMSE on held-out data, and a risk message such as
  "possible breach".
- **Operator loop.** Acknowledge the alert, tag a factory, and add a note. All three are persisted and appear
  in the alert history and the feedback panel.
- **Source outage.** Click **Simulate air feed outage**, then advance. The header pill turns to "1 feed
  degraded", the *Collect* stage turns amber, and the trend shows a gap rather than a zero. After three failed
  windows the feed is `OFFLINE`. End the outage and advance to recover.
- **Transient breach ≠ alert.** Select Zone C, then PM10, then 7d. A one-window spike to about 210 µg/m³ is
  flagged as an anomaly but produced **no alert**, because persistence requires 3 windows.
- A **PM10 alert** also opens in Zone A during the scenario (factory plus construction dust, above
  100 µg/m³). It is a genuine outcome of the simulated world and resolves shortly after window 12.

**Reset** (bottom bar, or `python -m app.seed.reset_demo`) rebuilds everything in about 40 s to replay.
The demo clock is an accelerated replay: one click equals one 15-minute window of simulated time. The history
ends 8 h before the moment of seeding, so there is room for the replay without ever producing data "from the
future".

## 4. How PS 13 is covered

| PS 13 need | Implementation |
|---|---|
| Real-time multi-source ingestion | Connectors (OpenAQ, India OGD, simulated air/water/factory/events) → validation → PostgreSQL |
| Geo-time alignment | PostGIS point-in-zone assignment; 15-min windows; lag features |
| Anomaly detection | Rolling robust baseline, z-score, anomalous windows excluded from the baseline |
| Source attribution | Lagged association + during-anomaly deviation, ranked, always labelled ESTIMATE |
| Forecasting | Three candidate models, held-out selection, uncertainty band, risk vs threshold |
| Alerting | Thresholds with persistence, confidence, recovery hysteresis and deadband; append-only log |
| Operator feedback | Acknowledge, dismiss, false positive, tag factory/event, sensor issue, note — persisted |
| Dashboard | Map, KPIs, trend, anomaly, attribution, forecast, alerts, log, source health, pipeline rail |

## 5. Architecture

```mermaid
flowchart LR
  subgraph Sources
    OA[OpenAQ v3] ; OGD[India OGD AQI] ; SIM[Simulated air / water / factory / events]
  end
  Sources --> CON[Connectors] --> VAL[Validation + quarantine] --> DB[(PostgreSQL + PostGIS)]
  DB --> ALN[Geo-time alignment + features] --> ANO[Anomaly detector] --> ATT[Attribution estimate]
  ALN --> FC[Forecast] ; ALN --> ALR[Threshold + persistence alerts]
  ATT --> ALR
  ANO & ATT & FC & ALR --> DB
  DB --> API[FastAPI /api/v1] <--> R[(Redis: cache, data_version, last-known-good)]
  API --> UI[React dashboard] -->|ack + feedback| API
  SCH[APScheduler workers] --> CON & ALN
```

The backend is layered: **routes → services → repositories**. Routes validate input and shape responses
(Pydantic schemas). Services hold all business logic and analytics. Repositories hold all SQL. The frontend
only displays values the API returns; it formats numbers and times, and never computes KPIs.

## 6. Tech stack

| Layer | Choice |
|---|---|
| Frontend | React 18, TypeScript (strict), Vite 5, Leaflet via react-leaflet, ECharts (tree-shaken), zustand |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Storage | PostgreSQL 16 + PostGIS 3.4 (TimescaleDB optional), Redis 7 |
| Analytics | pandas, NumPy, scikit-learn (ridge regression) |
| Jobs | APScheduler (modular jobs, replaceable by a queue) |
| Tests | pytest (real Postgres/PostGIS + Redis), Vitest + Testing Library, Playwright checks during the build |

## 7. Project structure

```
enviro-pulse/
├── docker-compose.yml
├── README.md
├── backend/
│   ├── Dockerfile, docker-entrypoint.sh, requirements*.txt, .env.example, alembic.ini, pytest.ini
│   ├── migrations/versions/        0001_core_schema.py, 0002_timescale_optional.py
│   ├── app/
│   │   ├── main.py                 FastAPI app, CORS, lifespan scheduler, error handler
│   │   ├── api/                    routes_* (zones, analytics, alerts, feedback, health, source_health, demo)
│   │   ├── services/               validation, ingestion, alignment, features, anomaly, attribution,
│   │   │                           forecast, alerts, feedback, pipeline, dashboard, demo_stream
│   │   ├── analytics/              metrics (indicative AQI), anomaly_detector, attribution_engine, forecast_engine
│   │   ├── repositories/           all SQL (zones, sensors, readings, factories, events, alerts, …)
│   │   ├── connectors/             openaq, ogd_aqi, cpcb (reference), water_sensor, factory, events, simulated
│   │   ├── simulation/             world (zones, sensors, factories, thresholds), model, stream (golden)
│   │   ├── workers/                runner, ingestion/alignment/analytics/alert workers
│   │   ├── seed/                   seed_database, reset_demo, generate_demo_stream, seed_if_empty
│   │   ├── models/                 db_models (SQLAlchemy), schemas (API contracts)
│   │   └── core/                   config, database, redis, logging, parameters, timeutil, dependencies
│   └── tests/                      48 tests (unit, DB pipeline, API, connectors, end-to-end golden)
└── frontend/
    ├── Dockerfile, nginx.conf, .env.example, vite.config.ts, tsconfig.json
    └── src/
        ├── pages/Dashboard/        page composition
        ├── components/             Header, ZoneSelector, SourceHealth, PipelineRail, KpiRow, PollutionMap,
        │                           TrendChart, AnomalyChart, AttributionChart, ForecastChart, AlertPanel,
        │                           AlertLog, ZoneDetailsDrawer, DemoDock, Panel
        ├── hooks/                  one data hook per panel + health polling
        ├── services/api.ts         the only module that talks to the backend
        ├── state/dashboardStore.ts shared selection state (zone, parameter, range)
        └── test/                   11 Vitest tests
```

## 8. Data sources and the simulated-data policy

| Source | Status in this prototype | What we do **not** claim |
|---|---|---|
| OpenAQ v3 (`openaq`) | Implemented (key in `X-API-Key` header). `OFFLINE` until `OPENAQ_API_KEY` is set | That all values are government-operated or real-time |
| India OGD real-time AQI (`ogd_aqi`) | Implemented. `OFFLINE` until `OGD_API_KEY` is set | That unrelated OGD datasets share its freshness |
| CPCB (`cpcb`) | Reference context only (NAQI breakpoints, NAAQS limits in threshold `basis`) | Any invented endpoint or field |
| Air / water sensors, factory ops, events | **SIMULATED DEMO STREAM** (deterministic, seed 13) | That simulated data is a physical sensor feed |

Where simulated data is labelled: source-health rows (`SIMULATED`), the water KPI badge, the trend badge,
sensor popups, the demo bar, and the `is_simulated` / `source_label` fields in the API.

Neither live connector has been exercised against the real APIs; the build environment's network blocks
them. Both are covered by mocked-HTTP tests (§22).

## 9. Ingestion and validation

Every record passes `services/validation.py` before storage. Validation normalises timestamps to UTC
(keeping the original string) and canonicalises unit aliases (`ug/m3` becomes `µg/m³`). It then checks:

- **Rejected into `quarantined_records`, with a reason code, never silently dropped:**
  - missing parameter or value field,
  - unknown parameter,
  - non-numeric value,
  - unit mismatch,
  - physically impossible value,
  - invalid or future timestamp,
  - no location,
  - a point outside every configured zone (PostGIS).
- **Accepted, with a quality flag:**
  - `VALID`;
  - `MISSING` (value kept as NULL, never 0);
  - `SUSPICIOUS` (plausibility bounds exceeded; excluded from zone means);
  - `STALE` (older than `STALE_AFTER_MINUTES`).
- **Duplicates:** a unique constraint on `(source, sensor_id, timestamp, parameter)` plus a
  `source_record_id` fingerprint. Re-sent batches are counted as duplicates and not inserted.

The seed deliberately injects 7 malformed and 20 duplicate records. All 7 are quarantined with a reason,
and all 20 are rejected as duplicates.

## 10. Geo-time alignment and features

Readings are assigned to zones by `ST_Contains` on zone polygons. They are bucketed into 15-minute windows
(`date_bin`). Per window and zone the pipeline computes:

- the mean of VALID readings;
- the valid-sensor count and a confidence (valid / expected sensors);
- a rolling mean and standard deviation (previous 96 windows, excluding anomalous windows);
- a z-score deviation and rate of change;
- factory output and 1–3-window lag features;
- event-active flags;
- the indicative AQI.

Every feature row stores its unit and a `source_window` description. Missing windows stay missing and are
never interpolated.

## 11. Anomaly detection

`analytics/anomaly_detector.py` detector `rolling-zscore-v1`:

- **Score:** z = (value − rolling mean) / rolling std over the previous 96 windows (24 h). A small floor on
  the standard deviation prevents divide-by-noise.
- **Anomaly:** |z| ≥ `ANOMALY_ZSCORE_THRESHOLD` (default 3).
- **Baseline hygiene:** windows already flagged are excluded from later baselines, so a sustained excursion
  cannot "teach" the baseline that it is normal.
- **Insufficient history:** fewer than 24 baseline windows returns `INSUFFICIENT_HISTORY`, and no anomaly is
  invented.
- **Scope:** an anomaly means unusual for this zone. It is **not** a threshold decision; alerts are
  evaluated separately.

## 12. Source attribution (estimate)

`analytics/attribution_engine.py` method `lagged-assoc-v1`. For an anomaly it scores each candidate in the
same zone (factories and events) over the previous 96 aligned windows:

- **Continuous candidates (factory output):**
  - Pearson correlation with the pollutant at lags 0–3 windows; the best lag is kept.
  - The candidate's deviation during the anomaly relative to its own history (σ).
- **Binary candidates (events):** association plus whether the event is active in the anomaly window versus
  how rarely it was active before.
- **Ranking:** a combined score in [0, 1]. Each result carries plain-language evidence, the time window, a
  data-quality summary and the method version.

Wording rules enforced in code and tests: results are *likely contributors* and an **ESTIMATE**. The scatter
caption reads *"Association only — not proof of causation."* A test scans API responses and all frontend
source for causal phrases. Weather (wind), which a real deployment would need to confirm transport, is
reported as `unavailable`.

## 13. Forecasting

`analytics/forecast_engine.py` produces the next 8 windows (2 h). Three candidates are fitted and scored on a
chronological hold-out:

- **persistence**,
- **seasonal naive (24 h)**,
- **ridge regression** on lag, diurnal and factory features (scikit-learn).

The model with the lowest held-out RMSE is used, and MAE, RMSE and every candidate's scores are returned.
In the seeded demo, `ridge_lag` typically wins (RMSE ≈ 6.0 vs persistence ≈ 6.3 for Zone A PM2.5).

- **Band:** ±1.96 · RMSE_holdout · √h, labelled "approximate". It is not a calibrated interval.
- **Risk:** reported against the configured threshold as `breach_predicted`, `possible_breach` (only the
  band reaches the threshold) or `below_threshold`.
- **Controlled states:** `INSUFFICIENT_HISTORY` (under 3 days), `INSUFFICIENT_RECENT_DATA` and
  `MODEL_ERROR`. No forecast is fabricated in any of these.

## 14. Thresholds and alerts

The thresholds are prototype operational triggers derived from CPCB NAAQS and water criteria, applied to
15-min zone means. They are not regulatory compliance determinations; each rule stores its `basis` text.

| Parameter | Rule | Persistence | Severity |
|---|---|---|---|
| PM2.5 | > 60 µg/m³ | 3 windows | high |
| PM10 | > 100 µg/m³ | 3 | medium |
| NO₂ | > 80 µg/m³ | 4 | medium |
| Turbidity | > 25 NTU | 2 | medium |
| Dissolved oxygen | < 4 mg/L | 2 | high |
| pH | > 8.5 or < 6.5 | 2 | medium |

Zone-specific rules override global ones. The engine (`services/alerts.py`) evaluates windows sequentially
with a per-rule watermark:

- **Opening an alert:** requires *persistence* consecutive breaching windows with confidence ≥
  `min_confidence`. Missing or low-confidence windows **hold** state; they count as neither breach nor
  recovery.
- **While open:** further breaches **update** the same alert. Duplicates are also blocked by a partial
  unique index (one open episode per zone, parameter and rule).
- **Recovery hysteresis:** the episode closes after `ALERT_CLEAR_WINDOWS` (2) consecutive **clearly
  normal** windows, meaning at least `ALERT_CLEAR_MARGIN_PCT` (5%) inside the limit. Values hovering just
  under the threshold keep the episode open. This was added after a single construction episode was
  observed splitting into two alerts.
- **Audit trail:** every step is written to the append-only `alert_events` log (created, notification
  dispatched, updated, recovering, acknowledged, feedback, resolved).
- **Late data:** it is stored and aggregated, but it does not retroactively trigger alerts for windows
  already evaluated.

## 15. Operator feedback loop

| Action | Effect |
|---|---|
| **Acknowledge** | `POST /alerts/{id}/acknowledge` sets the status to `acknowledged`. The episode stays open, so no duplicate alert is created. |
| **Dismiss / false positive** | Sets the alert to `dismissed` while the episode stays open. |
| **Confirm, tag factory, tag event, sensor issue, note** | Stored in `feedback`, with the contributor where relevant. |

All actions also go to the alert log. Feedback is persisted for future threshold and model recalibration.
The prototype does not yet retrain automatically from it.

## 16. Database

Nineteen tables, created **only** by Alembic migrations:

- **Core:** `zones` (PostGIS polygons), `sensors` (points), `readings`, `aqi_snapshots`,
  `water_observations`, `factories`, `factory_outputs`, `events`, `features`, `anomalies`, `attributions`,
  `forecasts`, `thresholds`, `alerts`, `feedback`, `source_health`.
- **Support:** `quarantined_records`, `alert_events`, `pipeline_state` (watermarks and demo state).

Migration `0002` turns `readings` and `features` into TimescaleDB hypertables **only if** the extension is
available; otherwise it is a no-op. The migrations were verified up → down → up on PostgreSQL 16 +
PostGIS 3.4. The TimescaleDB branch was not exercised.

## 17. API reference

Base path `/api/v1`. Interactive docs at `/docs`. Time-range endpoints accept `time_range` (1h–14d) **or**
an explicit `start` + `end`. Relative ranges end at the zone's newest data, not the wall clock, so a stalled
feed is never shown as current.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | API, DB (PostGIS version), Redis, scheduler, `data_version`, latest data time |
| GET | `/source-health` | Per-source status (HEALTHY / DEGRADED / OFFLINE / SIMULATED), last fetch, latency, error, last-known-good |
| GET | `/zones` | Zones with GeoJSON, latest indicative AQI, open alerts |
| GET | `/zones/{id}/summary` | KPIs, water status, threshold decisions, pipeline-stage status |
| GET | `/zones/{id}/map` | Sensors (latest value + quality flag), factories (24 h output), events, intensity |
| GET | `/zones/{id}/trends` | Zone means (gaps kept), factory series, event markers |
| GET | `/zones/{id}/anomalies` | Observed series, baseline band, anomaly records |
| GET | `/zones/{id}/attribution` | Ranked likely contributors (ESTIMATE), scatter data |
| GET | `/zones/{id}/forecast` | Prediction + band, validation metrics, risk |
| GET | `/alerts`, `/alerts/{id}` | Alert log and a single alert with its full history |
| POST | `/alerts/{id}/acknowledge` | Acknowledge (409 if not active) |
| POST / GET | `/feedback` | Record and list operator feedback |
| GET / POST | `/demo/status`, `/demo/tick`, `/demo/source-outage`, `/demo/reset` | Demo controls (disabled when `ENABLE_DEMO_CONTROLS=false`) |

Errors: 404 for an unknown zone or alert; 422 for invalid parameters or windows (with a message); 409 for
invalid state transitions. Unhandled errors return a generic 500, and the details are logged, never exposed.

## 18. Redis usage

- **`data_version` counter.** It is bumped whenever the pipeline writes results, an alert changes or
  feedback arrives. The dashboard polls `/health` and refetches panels only when it changes.
- **Summary cache.** It is keyed by zone, window and `data_version`, so the cache can never serve stale
  KPIs.
- **Last-known-good batch per source.** It is shown when a feed degrades.
- **Degradation, not failure.** If Redis is down, `/health` reports `degraded` and the API keeps serving from
  PostgreSQL.

## 19. Background workers

`app/workers/runner.py` (APScheduler; runs inside the API when `ENABLE_SCHEDULER=true`, or standalone with
`python -m app.workers.runner`):

- **External air ingestion,** every `INGEST_INTERVAL_SECONDS`. Unconfigured sources are marked `OFFLINE`.
  Failures move a source HEALTHY → DEGRADED → OFFLINE after 3 consecutive failures.
- **Pipeline,** every `PIPELINE_INTERVAL_SECONDS`: alignment, analytics, alerts and forecasts for anything
  new since the watermark.
- **Optional automatic demo tick** (`DEMO_STREAM_AUTO=true`).

A failing job is logged and never stops the scheduler.

**Concurrency.** Every pipeline mutation takes a PostgreSQL transaction-scoped advisory lock: demo ticks,
watermark processing and outage toggles. Overlapping requests therefore queue instead of racing. The cases
covered are two browser tabs, *Play* plus a click, and the scheduler overlapping a tick. Without the lock,
four simultaneous ticks were measured processing the same window and losing three advances. A regression
test now covers this. The jobs are plain functions, so they can move to
Celery, RQ or Arq without changing the API.

## 20. Frontend

One page, organised around the question each panel answers:

- **Pollution map:** *Where is it happening?*
- **Trend:** *When did it change?*
- **Anomaly timeline:** *Is this unusual?*
- **Source attribution:** *What is the likely contributor?*
- **Forecast:** *What might happen next?*
- **Current alert:** *What should the officer do?*
- **Alert log**, **operator feedback**, **source health** and the **zone details** drawer.

The **pipeline rail** under the header shows the live status of the six stages and jumps to each panel.
All panels share one selection (zone, parameter, range). Selecting a zone in the dropdown or on the map
updates everything.

Each panel has loading, error and empty states. On a failed refresh the last valid data stays visible with
an error line. Status states such as *Insufficient history* or *Nothing to explain* come straight from the
API.

The layout is responsive from 390 px phones to wide desktops. On phones the header scrolls away and the demo
controls start collapsed. Times are shown in the viewer's local time zone.

## 21. Configuration (environment variables)

All settings live in `backend/.env.example`, with comments; every field in `app/core/config.py` is listed
there. The most important:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://enviro:enviro@localhost:5432/enviropulse` | PostgreSQL/PostGIS |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis |
| `CORS_ORIGINS` | localhost:5173 / 4173 | Allowed browser origins |
| `OPENAQ_API_KEY`, `OGD_API_KEY` | empty | Enable live air connectors |
| `ENABLE_SCHEDULER` | `true` | Run background jobs inside the API |
| `ENABLE_DEMO_CONTROLS` | `true` | Demo endpoints (**set `false` when shared**) |
| `DEFAULT_TIME_WINDOW_MINUTES` | 15 | Alignment window |
| `ANOMALY_ZSCORE_THRESHOLD` | 3.0 | Anomaly cut-off |
| `FORECAST_HORIZON` | 8 | Forecast windows |
| `ALERT_CLEAR_WINDOWS` / `ALERT_CLEAR_MARGIN_PCT` | 2 / 5.0 | Recovery hysteresis and deadband |
| `HISTORY_DAYS` / `HISTORY_LAG_HOURS` | 14 / 8 | Seeded history length and replay headroom |

Frontend (`frontend/.env.example`): `VITE_API_BASE_URL`, `VITE_POLL_INTERVAL_MS`. These are public; never put
secrets in `VITE_` variables.

## 22. Testing and results

**Backend: 48 tests.** They run against a real PostgreSQL/PostGIS test database created by the Alembic
migrations and Redis DB 1:

```bash
createdb -O enviro enviropulse_test   # plus: CREATE EXTENSION postgis (superuser)
cd backend
TEST_DATABASE_URL=postgresql+psycopg://enviro:enviro@localhost:5432/enviropulse_test \
TEST_REDIS_URL=redis://localhost:6379/1 python -m pytest
```

| File | Covers |
|---|---|
| `test_validation.py` | UTC normalisation, missing ≠ 0, flags, every rejection reason, dedupe fingerprint, alert deadband |
| `test_analytics_engines.py` | Detector (spike, sustained, missing, threshold ≠ anomaly), attribution recovers an injected lag, forecast states and band, NAQI |
| `test_pipeline_db.py` | PostGIS assignment, quarantine, duplicates, NULL preservation, features/lags, Zone C spike, transient breach ≠ alert, one alert per episode, zone overrides, DB-level duplicate block, insufficient history |
| `test_api.py` | Every endpoint's contract, honest source health, units/timestamps, ESTIMATE wording, no causal phrases, validation errors, OpenAPI |
| `test_connectors.py` | OpenAQ and OGD mapping with mocked HTTP, key in header, NA → missing, not-configured and failure behaviour |
| `test_zz_e2e_golden.py` | Reset → golden scenario **through the API**: new readings stored, aligned, anomaly, attribution, persistence, alert, forecast, ack, feedback, resolution; outage degrade → offline → recover; concurrent ticks serialised |

**Frontend: 11 Vitest tests.** They cover KPI rendering (values, loading, no-data), alert card fields, the
API client (URLs, error messages, unreachable backend, POST body), store synchronisation, and a wording guard
over all source files. `npm run build` passes with strict TypeScript.

**Browser verification** (Playwright + Chromium against the live backend during the build):

- The page loads with no page errors.
- Zone and parameter switching, acknowledge, feedback, advancing the stream, the outage → degraded →
  recovery cycle, and the zone drawer all work.
- Layouts were checked at 390, 768, 1024 and 1440 px, with no horizontal page overflow.

## 23. Acceptance criteria evidence

| ID | Criterion | Evidence |
|---|---|---|
| AC-01 | Dashboard loads, shows source/health | Playwright run: 0 page errors; header source-health pill + popover |
| AC-02 | Zone selection switches all panels | Shared store; Playwright zone switch; `test_api` + store test |
| AC-03 | Map renders zones, sensors, industry | `test_map_layers`; screenshots |
| AC-04 | Trend timestamps/units correct | `test_trends_timestamps_units_and_context` |
| AC-05 | Spike → baseline + anomaly | `test_anomaly_detected_for_zone_c_spike`, `test_anomalies_show_baseline_band` |
| AC-06 | Ranked contributors with estimate wording | `test_attribution_is_labelled_estimate` (recovers fac_b2 / fac_a1 ground truth) |
| AC-07 | Forecast + bounds with enough history | `test_forecast_response`, `test_forecast_returns_validated_prediction_band` |
| AC-08 | Controlled status on insufficient data | `test_insufficient_history_returns_controlled_states`, `test_forecast_insufficient_history_is_controlled` |
| AC-09 | Threshold breach detected | `test_persistent_breach_created_one_alert_with_log`, golden e2e |
| AC-10 | One-window breach ≠ alert | `test_transient_breach_does_not_create_alert` |
| AC-11 | Alert card fields | `test_alerts_list_and_detail`; Vitest `AlertCard` |
| AC-12 | Alert persists and is queryable | `/alerts`, `/alerts/{id}` log; golden e2e |
| AC-13 | Ack/feedback persisted | Golden e2e (ack 200, re-ack 409, feedback listed); Playwright |
| AC-14 | Outage → degraded, no fresh-data claim | `test_source_outage_degrades_and_recovers`; Playwright |
| AC-15 | No "proven cause" wording | `test_no_response_claims_causation`; Vitest wording guard |
| AC-16 | New observation → ingestion → analytics → dashboard/alert | `test_golden_scenario_end_to_end` |

## 24. Known limitations

| Area | Limitation |
|---|---|
| **Data** | Zones are synthetic polygons in the Mumbai–Navi Mumbai region (Thane–Belapur, Taloja, Trombay). Factories are fictional. All demo data is simulated. The indicative AQI follows NAQI breakpoints on 15-min means and is **not** an official AQI. |
| **Live sources** | The OpenAQ and OGD connectors were not tested against the live APIs; the OGD field semantics should be verified before production use. No CPCB API is called. |
| **Demo clock** | The demo clock is an accelerated replay (1 click = 1 window). History content varies slightly with the time of day the seed runs, because of the diurnal cycle. The golden scenario itself is fixed. |
| **Analytics** | No weather or wind data, so attribution cannot confirm transport. The forecast band is an approximation, not a calibrated interval. No Isolation Forest or seasonal decomposition; the detector is a rolling z-score. Feedback is stored but not yet used to retrain. Late data does not retroactively trigger alerts. |
| **Platform** | No authentication or roles; demo endpoints must be disabled when shared. Notifications are in-app only (no SMS or email). Docker Compose and the TimescaleDB path were not executed in the build environment. Map tiles and the web font load from public CDNs (OpenStreetMap, Google Fonts). |

## 25. Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard says "Cannot reach the EnviroPulse API" | Start the backend; check `VITE_API_BASE_URL`; check `CORS_ORIGINS` includes the dashboard origin |
| `type "geometry" does not exist` during migrate | Run `CREATE EXTENSION postgis;` as a superuser in the database |
| Seed says "already seeded" | Use `python -m app.seed.reset_demo` |
| "The simulated clock has caught up with real time" | The replay reached the present; reset the demo |
| All panels "Insufficient history" | The database was migrated but not seeded; run the seed |
| Health shows Redis degraded | Start Redis or fix `REDIS_URL`; the API keeps working without the cache |
| Map has no background | The browser cannot reach tile.openstreetmap.org (offline / firewall); overlays still render |
| Tests fail to connect | Create `enviropulse_test` with PostGIS and set `TEST_DATABASE_URL` / `TEST_REDIS_URL` |

## 26. Deployment notes

The stack is four provider-neutral services: frontend (static files on nginx), backend (FastAPI + scheduler),
PostgreSQL + PostGIS, and Redis. For anything beyond a demo:

- Set `ENABLE_DEMO_CONTROLS=false`.
- Put the API behind authentication.
- Restrict `CORS_ORIGINS`.
- Store keys in a secret manager.
- Run the scheduler as its own process (`python -m app.workers.runner`) with one API process per replica.
- Use managed PostgreSQL with PostGIS and TimescaleDB.

Before any regulatory use, calibrate thresholds and models with real sensor history and operator feedback.

---

### Screenshots

Captured with headless Chromium in the build sandbox, which blocks external hosts. The map therefore has no
OpenStreetMap tiles and text uses the fallback font; both load normally on a regular network.

- `docs/screenshots/dashboard-alert-window8.png`: golden scenario at window 8 (active PM2.5 alert)
- `docs/screenshots/attribution-forecast-log.png`: attribution estimate, forecast band, alert log
- `docs/screenshots/mobile-390px.png`: phone layout
