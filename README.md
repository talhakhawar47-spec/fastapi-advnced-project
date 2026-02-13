# FastAPI Advanced Project

## Run the project locally

### 1) Create and activate a virtual environment

#### Windows PowerShell
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### macOS/Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2) Install dependencies
```bash
uv sync
```

### 3) Start the server

Primary command:
```bash
python -m uvicorn app.app:app --host 0.0.0.0 --port 8001 --reload
```

Alternative command (if your environment supports `uv run` correctly):
```bash
uv run python -m uvicorn app.app:app --host 0.0.0.0 --port 8001 --reload
```

You can also run the helper module:
```bash
python app/main.py
```

### 4) Open docs
- Swagger UI: `http://127.0.0.1:8001/docs`

## Windows troubleshooting

### `Failed to canonicalize script path` when running `uv run uvicorn ...`
Use one of these instead:

```powershell
python -m uvicorn app.app:app --host 0.0.0.0 --port 8001 --reload
```

or

```powershell
uv run python -m uvicorn app.app:app --host 0.0.0.0 --port 8001 --reload
```

This bypasses direct script resolution issues for `uvicorn` on some Windows setups.