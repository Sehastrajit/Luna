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

## Chat

`luna chat` uses the same `/api/chat/stream` path as the web and Electron UI. Terminal chat supports normal conversation plus tool execution, web research, workspace file creation, installed skills, agent tasks, Google/Microsoft workspace tools, plans, proactive messages, and backend command events.

```powershell
luna chat
luna chat "research the SEC and show references"
luna chat --yes "create the requested workspace file"
luna chat --no "try the task but deny any risky confirmation"
```

Inside chat:

- `/new`: start a fresh conversation.
- `/help`: show terminal chat commands.
- `/exit` or `/quit`: leave chat.

When a tool requires confirmation, the CLI prompts for approval. Use `--yes` to auto-approve confirmations for a one-shot or session, and `--no` to auto-deny them.
