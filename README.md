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

### Quality checks
```bash
pytest -q
ruff check .
black .
mypy .
```
