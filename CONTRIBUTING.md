# Contributing

Thanks for your interest in Luna.

## Development setup

1. Install Node.js, Python, and Ollama.
2. Copy `.env.example` to `.env` and fill only the keys needed for your local setup.
3. Install dependencies:

```powershell
npm install
cd frontend
npm install
```

4. Install backend dependencies:

```powershell
pip install -r backend/requirements.txt
```

5. Start the app:

```powershell
npm run luna -- dev
```

## Pull requests

- Read `docs/ARCHITECTURE.md` before making broad changes.
- Read `docs/PROCESSES.md` before changing background jobs, voice runtime, or proactive behavior.
- Use `docs/CLI.md` and `docs/VSCODE.md` for common local workflows.
- Keep runtime data, logs, local databases, generated builds, and secrets out of commits.
- Prefer focused changes with a clear description of behavior and testing.
- Run relevant frontend or backend checks before opening a pull request.
- Keep routers thin. Put provider logic in `backend/services/`.
- Add background/runtime work as a process under `backend/processes/`.
- Keep large UI features split by feature folder under `frontend/src/components/`.

## Privacy

Do not submit personal chat logs, tokens, local memory databases, `.env` files, or generated runtime data.
