# AGENTS.md — QA Checklist Generator (Python, local, RAG, screenshots)

> Audience: AI coding agents (Codex / Cursor Agent) working inside this repository.
> Goal: build a local Python app that generates QA checklists (XLSX) using:
> - Knowledge base from Avto.pro Help Center (scraped + RAG)
> - Free LLM via gpt4free (g4f)
> - Screenshot understanding (start with OCR; optional multimodal later)

---

## 0) Golden rules (read first)

- **Plan first, then code.** For any non-trivial task: produce a short plan (files to touch, tests to add), then implement.
- **Keep diffs small.** Prefer incremental PR-style changes. Don’t refactor unrelated code.
- **No secrets.** Never add API keys, cookies, tokens, HAR files, or personal data to the repo.
- **Deterministic where possible.** LLM calls are flaky—wrap them, add retries/timeouts, and mock in tests.
- **Respect the target website.** Scraping must be polite: rate limit, cache, and avoid unnecessary load.
- **Ask before adding heavy deps.** If you need a new major dependency (DB, framework, big ML model), explain why first.

---

## 1) Quick commands (copy/paste)

> Prefer these exact commands when you need to run / validate changes.

### Setup
```bash
python -m venv .venv
# mac/linux
source .venv/bin/activate
# windows (powershell)
# .venv\Scripts\Activate.ps1

python -m pip install -U pip
pip install -r requirements.txt

Run (dev)
python -m app.main
# or (if FastAPI)
# uvicorn app.main:app --reload --port 8000

Lint / Format / Typecheck
ruff check .
black .
mypy .

Tests
pytest -q

Build / refresh knowledge base (Help Center → chunks → vector DB)
python -m scripts.scrape_helpcenter --out data/raw_helpcenter
python -m scripts.build_kb --in data/raw_helpcenter --out data/kb

2) Tech constraints & choices

Python web app (local-first). Start simple: FastAPI (recommended) or Flask.

LLM: gpt4free (g4f).

Prefer using its OpenAI-compatible “Interference API” when possible:

Base URL: http://localhost:1337/v1

Swagger: http://localhost:1337/docs

The app must work even when providers are flaky: add fallback & good errors.

RAG / Vector DB (free):

Default: Chroma local persistence.

Embeddings: SentenceTransformers multilingual model (configurable).

Screenshots:

Phase 1: OCR (pytesseract + optional opencv-python).

Phase 2 (optional): multimodal model (only behind feature flag).

3) Repository structure (expected)

Keep code modular; avoid a single “god file”.
app/
  main.py                 # app entrypoint (API + UI wiring)
  config.py               # env + settings
  api/                    # routes, schemas
  services/
    llm/                  # g4f client wrapper + prompts
    rag/                  # retrieval pipeline
    kb/                   # ingestion (scrape → clean → chunk → embed → store)
    checklist/            # checklist generator + XLSX exporter
    vision/               # OCR + screenshot processing
  templates/
    checklist_template.xlsx
  domain/
    models.py             # pydantic/domain models

scripts/
  scrape_helpcenter.py
  build_kb.py

tests/
  test_scraper.py
  test_chunking.py
  test_retrieval.py
  test_checklist_export.py

data/                     # local artifacts (gitignored)
  raw_helpcenter/
  kb/
  chroma/

Note: data/ must be in .gitignore (large/derived artifacts).

4) Environment variables (single source of truth)

Put defaults in app/config.py. Document them in README as they appear.

Recommended env vars:

APP_PORT=8000

G4F_BASE_URL=http://localhost:1337/v1 (optional; if not set, call g4f Python client)

G4F_MODEL=gpt-4o-mini (example; must be configurable)

G4F_PROVIDER= (optional provider pin)

KB_PERSIST_DIR=data/chroma

EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2

SCRAPE_BASE_URL=https://avto.pro/helpcenter/

SCRAPE_RATE_LIMIT_SECONDS=1.0

Never hardcode these in code. Always read from env/config.

5) Scraping / ingestion rules (Help Center → KB)
Scraper requirements

Fetch only within SCRAPE_BASE_URL.

Use a clear User-Agent string.

Respect rate limiting (SCRAPE_RATE_LIMIT_SECONDS) and caching.

Store raw HTML and extracted text (for reproducibility and debugging).

Keep per-page metadata:

url, title, language, fetched_at, hash, breadcrumbs/category if available.

Text cleaning & chunking

Strip nav/footer/boilerplate.

Preserve headings; include them in chunk metadata.

Chunk target: 300–800 tokens per chunk (tune later).

Each chunk must carry:

source_url, doc_title, section_heading, chunk_id, text

Vector store

Chroma persisted locally (KB_PERSIST_DIR).

Provide CLI commands:

rebuild KB from scratch

incremental update (if hashes changed)

6) RAG behavior (retrieval → prompt → generation)
Retrieval

Use semantic search (top_k configurable, default 5).

Return both text + citations (source URLs) to the generator.

If retrieval confidence is low:

ask clarifying questions before generating a full checklist.

Prompting contract (must follow)

The checklist generator must output a structured intermediate format first (JSON).

Then export to XLSX from that JSON (never parse freeform text if avoidable).

Proposed JSON shape:
{
  "title": "…",
  "meta": { "author": "", "pbi": "", "scope": "" },
  "sections": [
    {
      "name": "…",
      "items": [
        {
          "check": "…",
          "expected": "…",
          "notes": "",
          "for_dev": ""
        }
      ]
    }
  ]
}

7) Checklist XLSX format (template-driven)

We use app/templates/checklist_template.xlsx as the canonical format.

Write into these columns:

A: Проверка

B: Ожидаемый результат

C–E: Прогон 1..3 (leave empty by default)

F: Примечание

G: Для разработчика

Preserve:

formatting, column widths, wrapping, merged cells, section rows.

Metadata (optional, if present in template):

Keep “Автор” / “PBI” blocks if they exist.

If you add new metadata fields, update the template + exporter + tests together.

8) Screenshot processing (phase 1)

Accept PNG/JPG uploads.

Run OCR → produce:

extracted_text

(optional) detected UI keywords (buttons/labels)

Feed extracted_text into the same RAG pipeline as “additional context” (not into KB unless user explicitly asks to store it).

All OCR code must be behind a small interface:

extract_text(image_bytes) -> str

So we can swap OCR engines later.

9) Testing requirements

Minimum test coverage for each change:

Scraper: parses at least one saved HTML fixture deterministically.

Chunking: stable chunk boundaries for a known input.

Retrieval: given a small toy KB, query returns expected chunk(s).

LLM wrapper: mocked (never call network in unit tests).

XLSX export: produces a file; validate key cells and formatting basics.

Use pytest and unittest.mock.
For any network call, add an injectable client and mock it.

10) Logging & error handling

Use structured logs (JSON or key-value).

Never log full prompts containing user secrets.

User-facing errors should be actionable:

“KB not built. Run: python -m scripts.build_kb …”

“g4f unavailable. Start Interference API or set provider.”

11) Definition of done (DoD)

A task is “done” only if:

Code builds/runs locally

Tests pass (pytest)

Lint passes (ruff, black, mypy if configured)

Any new behavior is documented (README or docs/)

No secrets or large artifacts were committed

12) What to ask the user (when unclear)

Before implementing, clarify:

UI choice (web chat vs telegram bot)

Required checklist structure changes

Which Help Center language(s) to index

Whether screenshots should be stored in KB or only used per-session

If in doubt, implement the smallest useful piece and keep it extensible.