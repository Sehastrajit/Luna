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
- Run `npm run test:smoke` before opening a pull request.
- Run `npm run build` when changing the frontend.
- Keep routers thin. Put provider logic in `backend/services/`.
- Add background/runtime work as a process under `backend/processes/`.
- Keep large UI features split by feature folder under `frontend/src/components/`.

## Automated testing

Use the smoke suite for the common contributor path:

```powershell
npm run test:smoke
```

It runs backend syntax checks, CLI syntax checks, and the separated tool tests in `tests/tools/`.

Use the tool-only suite when changing tool routing, app launcher profiles, Spotify commands, or the tool registry:

```powershell
npm run test:tools
```

The tool smoke tests are intentionally non-destructive. They do not launch apps, click, type, lock the screen, switch audio devices, or start playback. Tests that need persistence use an in-memory database or write a temporary workspace/agent-task record and clean it up.

## Privacy

Do not submit personal chat logs, tokens, local memory databases, `.env` files, or generated runtime data.
