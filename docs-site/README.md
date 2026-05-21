# LUNA Docs Site

A production-ready Next.js documentation website for open source contributors working on the L.U.N.A. repository.

## Install

From the project root:

```powershell
cd docs-site
npm install
```

## Run locally

```powershell
npm run dev
```

Open `http://localhost:3000`.

## Use from the repository root

```powershell
npm run docs
```

## Build and start

```powershell
npm run docs:build
npm run docs:start
```

## Pages

- `/`: landing page with quick links and repo overview
- `/getting-started`: setup and local development instructions
- `/architecture`: application architecture and boundaries
- `/cli`: repository CLI command reference
- `/codebase`: deep dive on implementation, entrypoints, and runtime patterns
- `/contributing`: contributor and PR guidelines
- `/project-structure`: repository layout and module ownership
- `/environment`: runtime configuration and `.env` guidance

## Theme

The docs UI supports light and dark modes. Use the top-bar toggle to switch themes; the selected theme is saved in `localStorage` and falls back to the system color scheme on first visit.
