## Avto.pro QA Checklist Generator (skeleton)

Local FastAPI scaffold for the QA checklist generator (Python 3.11+).

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
