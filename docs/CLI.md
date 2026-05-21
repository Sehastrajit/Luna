# CLI

L.U.N.A. includes a small Node-based CLI for common contributor workflows.

Run it from the repo root:

```powershell
npm run luna -- <command>
```

After installing the package globally or linking it locally, the `luna` binary is also available:

```powershell
npm link
luna doctor
```

## Commands

- `help`: show command help.
- `doctor`: check Node, npm, and Python availability.
- `dev`: start Vite and Electron together.
- `dev:lan`: start development mode with Vite exposed on the LAN.
- `web`: start the FastAPI backend and browser UI without Electron.
- `web:lan`: start the backend and expose the browser UI on the LAN for phones, tablets, and other computers.
- `backend`: start only the FastAPI backend.
- `frontend`: start only the Vite frontend.
- `electron`: start only the Electron shell.
- `build`: build the frontend.
- `dist`: build the frontend and Windows Electron package.
- `check`: run lightweight backend syntax checks.
- `processes`: print registered backend processes as JSON.
- `clean`: remove local runtime/build artifacts ignored by git.

The CLI intentionally wraps existing npm and Python entrypoints. Feature-specific commands should stay thin and delegate to the owning process, service, or package script.
