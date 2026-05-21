# Contributing to L.U.N.A.

Thanks for your interest in Luna. Read this before you start.

---

## Attribution requirement

Luna is MIT-licensed. MIT lets you use, fork, and redistribute freely — but **attribution is required and expected**:

- **Keep the copyright notice** in any source file you copy. The MIT license requires this.
- **Credit Luna visibly** if your project is built on or derived from Luna code:
  - In your README: `Built with [L.U.N.A.](https://github.com/Sehastrajit/Luna)`
  - In any public UI or about page that ships Luna-derived code
- **Do not remove or obscure** the `L.U.N.A.` name, the copyright header, or the `LICENSE` file when distributing.
- **Do not claim Luna as your own original work** in a way that misleads users.

Forking to build something new is great — just be honest about where it came from.

---

## Development setup

1. Install Node.js 18+, Python 3.10+, and [Ollama](https://ollama.com/).
2. Copy `.env.example` to `.env` and fill only the keys you need locally.
3. Install dependencies:

```powershell
npm install
cd frontend && npm install && cd ..
pip install -r backend/requirements.txt
```

4. Start the app:

```powershell
npm run luna -- dev
```

---

## Pull requests

- Read `docs/ARCHITECTURE.md` before making broad structural changes.
- Read `docs/PROCESSES.md` before touching background jobs, voice runtime, or proactive behaviour.
- Keep routers thin — put provider logic in `backend/services/`.
- Add background/runtime work as a process under `backend/processes/`.
- Split large UI features by folder under `frontend/src/components/`.
- Run `npm run test:smoke` before opening a PR.
- Run `npm run build` when changing the frontend.
- One clear behaviour per PR. Include a description of what changed and how to test it.

---

## Testing

```powershell
npm run test:smoke   # backend syntax + CLI + tool wiring (run before every PR)
npm run test:tools   # tool-only suite (run when changing tool routing or registry)
npm run build        # frontend type check + bundle (run when changing frontend)
```

The smoke tests are non-destructive — they do not launch apps, click, type, lock the screen, switch audio devices, or start playback.

---

## What not to commit

- `.env`, API keys, tokens, credentials of any kind
- Local databases (`*.db`, `*.sqlite`)
- Chat logs, memory stores, personality state files
- Generated build artifacts, `node_modules/`, `__pycache__/`
- Personal runtime data from `data/`

---

## Code style

- Python: follow PEP 8. Keep routers thin; logic lives in services.
- TypeScript: strict mode is on. Prefer named exports. Components in feature folders.
- No non-ASCII characters in backend log messages (Windows `cp1252` compatibility).

---

## Questions

Open a [GitHub Discussion](https://github.com/Sehastrajit/Luna/discussions) for questions about architecture or approach before writing code. Issues are for bugs and confirmed feature requests.
