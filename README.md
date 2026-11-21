# ctp-projects

Run the backend and frontend in two terminals.

## Backend (http://localhost:8000)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip ...
.venv/bin/uvicorn app.main:app --reload         # Windows: .venv\Scripts\uvicorn ...
```

## Frontend (http://localhost:5173)

```bash
cd frontend
npm install
npm run dev
```

The Vite dev server forwards `/api/*` to the backend on port 8000, so no extra config is needed.
To use a backend somewhere else, set `VITE_API_URL` (e.g. `VITE_API_URL=http://localhost:8000 npm run dev`).
