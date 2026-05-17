# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single FastAPI app exposes **two independent OAI-PMH 2.0 repositories**, each backed by a different MongoDB database:

- **CERIF repository** (`/oai`) — maps documents from the `kahi` database to CERIF 1.2 / OpenAIRE profile XML. Logic in `backend/src/oai.py`, mapping in `backend/src/cerif.py`. `metadataPrefix=oai_cerif_openaire`.
- **LaReferencia repository** (`/lareferencia/oai`) — serves harvested DSpace records from the `oxomoc_colombia` database. Logic in `backend/src/lareferencia.py`. `metadataPrefix=dim`.

A Next.js + Ant Design frontend (`frontend/`) provides explorer/documentation UIs and proxies API calls to the backend.

## Commands

Backend (Python ≥ 3.9):
```bash
pip install -r requirements.txt && pip install -e .
uvicorn backend.src.app:app --host 0.0.0.0 --port 8000 --reload   # dev
impactu_oaiserver --port 8000                                     # installed console script
./manage.sh start|stop|restart|status|logs [--dev]                # background process manager
impactu_oaiserver --validation 50                                 # cap total records served (for the validator)
```

Frontend (Next.js, port 3000):
```bash
cd frontend && npm install && npm run dev   # dev
npm run build && npm start                  # production
```

Docker (deployment; `network_mode: host`, backend on 9091, frontend on 9090):
```bash
docker compose build && docker compose up -d
```

OpenAIRE CRIS validation of the CERIF endpoint runs from `docker/openaire-validator/` — see its README.

There is **no automated test suite** in this repo; verify changes by exercising the OAI-PMH verbs directly (e.g. `curl` against `?verb=...`).

## Architecture

**Two-repository pattern.** `app.py` is a thin HTTP layer: it builds the effective request URL from `x-forwarded-host` / `x-forwarded-proto` headers (so OAI responses reflect the real public URL behind a reverse proxy) and dispatches to `handle_oai()` or `handle_lareferencia()`. Each repository module owns all OAI-PMH logic for its database.

**MongoDB access** (`mongo_client.py`): `get_db()` returns the `kahi` database and lazily creates pagination indexes; `get_lareferencia_db()` returns `oxomoc_colombia` read-only (no index creation). A single shared `MongoClient` is reused.

**CERIF repository** (`oai.py` + `cerif.py`): `OAI_COLLECTIONS` lists the `kahi` collections harvested (`works`, `patents`, `events`, `projects`, `person`, `affiliations`, `sources`, `subjects`) — **this list and its order are baked into resumption tokens**, so changing it breaks in-flight harvests. OAI sets (`openaire_cris_*`) map to one or more collections. `cerif.py` maps each document type to its CERIF/OpenAIRE XML element.

**LaReferencia repository** (`lareferencia.py`): the `oxomoc_colombia` database holds one `dspace_<acronym>_records` collection per Colombian institution. Each document is `{_id, "OAI-PMH": {...}}` where the `OAI-PMH` value is the original DSpace OAI response parsed with `xmltodict`. Serving a record means extracting `OAI-PMH.GetRecord.record` and converting the dict back to XML with `xmltodict.unparse` — header elements are rebuilt in lxml (OAI namespace) and the `dim:dim` payload is appended as-is. Each institution is an OAI set (`setSpec` = acronym); `setName` comes from the matching `dspace_<acronym>_identity` collection.

**Pagination.** Both repositories walk their collections in a fixed order, carrying a base64-encoded JSON resumption token with `coll_index`, `last_id`, `served`, the active filters, and (LaReferencia) `pageSize` and `total`. Records are sorted by `_id`; the token resumes with `_id > last_id`. LaReferencia adds `completeListSize` to the token and emits an empty closing `<resumptionToken>` on the final page of a paginated harvest.

**Frontend** (`frontend/`): Next.js Pages Router with Ant Design (locale `es_ES`). `next.config.js` `rewrites()` proxy `/oai`, `/stats`, `/lareferencia/oai`, `/lareferencia/stats` to `BACKEND_URL` (a build arg). Pages fetch OAI XML and parse it client-side with `DOMParser`. Routes `/lareferencia` and `/lareferencia/instituciones` are Next.js pages — the harvest endpoint deliberately lives at `/lareferencia/oai` to avoid colliding with the website route.

## Conventions

- Do not commit or push changes without explicit user confirmation.
- Configuration is environment-driven: `MONGO_URI`, `DB_NAME` (default `kahi`), `LAREFERENCIA_DB_NAME` (default `oxomoc_colombia`), `OAI_BASE_URL`, `LAREFERENCIA_BASE_URL`, `PORT`, and the frontend `BACKEND_URL` build arg. See `.env.example`.
