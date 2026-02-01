## Avto.pro QA Checklist Generator (skeleton)

Local FastAPI scaffold for the QA checklist generator (Python 3.11+).

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# one-time for browser automation (auth pages)
playwright install chromium
```

### Run dev server
```bash
uvicorn app.main:app --reload --port 8000
```

Endpoints:
- `GET /health` → `{"status": "ok"}`
- `GET /ready` → 503 if `KB_PERSIST_DIR` is missing (default `data/chroma`)
- `POST /llm/smoke` → basic LLM connectivity check

### LLM backend (g4f Interference API)
- Defaults: `G4F_BASE_URL=http://localhost:1337/v1`, `G4F_MODEL=gpt-4o-mini`, `G4F_API_KEY=secret`
- Docker (slim image): `docker pull hlohaus789/g4f && docker run --rm -p 1337:1337 hlohaus789/g4f:latest`
- Python: `python -m g4f.api.run --host 0.0.0.0 --port 1337`
- If you see `Form data requires "python-multipart"`, install: `pip install python-multipart`
- If the self-hosted API returns 401/“.har file” errors, either unset `G4F_BASE_URL` (to force Python client) or set `G4F_PROVIDER=ApiAirforce` for the g4f Python fallback.
- cURL check:
```bash
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer secret" \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"ping"}]}'
```

### Help Center scrape (RU/UA/PL/ES/PT)
- Run: `python -m scripts.scrape_helpcenter --sites ru,ua,pl,es,pt --download-assets 0`
- Auth-only pages via Playwright storage_state:
  1) `python -m scripts.capture_auth_state --site ru --out .secrets/auth/ru.json`
  2) `python -m scripts.scrape_helpcenter --sites ru --auth-state-dir .secrets/auth --download-assets 0 --force`
- Output: `data/helpcenter/raw/<site_code>/*.html`, `data/helpcenter/parsed/<site_code>/*.json|.md`, assets in `data/helpcenter/assets/<site_code>/`
- Use `--max-pages N` for quick debug (0 = all). `--force` to re-download even if parsed exists.

### Help Center preprocessing (chunks for RAG)
- Run: `python -m scripts.preprocess_helpcenter --sites ru,ua,pl,es,pt --force 1`
- Outputs: `data/helpcenter/chunks/<site_code>/chunks.jsonl` and `index.json` (summary + hash cache)
- Params snapshot: `data/helpcenter/chunks/_params.json`
- Tunables: env (`CHUNK_SIZE_CHARS`, `CHUNK_OVERLAP_CHARS`, `CHUNK_MIN_CHARS`) or CLI flags `--chunk-size-chars` etc.
- No embeddings/vector store yet — only normalized chunks + metadata.

### Audit chunks
- Run: `python -m scripts.kb_audit --sites ru,ua,pl,es,pt`
- Output: `data/helpcenter/audit_report.json` (length stats, top shortest/longest IDs, per-category/section counts)

### LLM smoke tests
- CLI: `python -m scripts.llm_smoke_test --prompt "Say this is a test"`
- API (Swagger UI): open `http://127.0.0.1:8000/docs` and call `POST /llm/smoke`

### Quality checks
```bash
pytest -q
ruff check .
black .
mypy .
```
