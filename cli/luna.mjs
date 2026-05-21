#!/usr/bin/env node
/**
 * L.U.N.A. CLI
 *
 * Install globally:  npm install -g .   (run once from project root)
 * Then use:          luna <command>
 *
 * Without global install:  npm run luna -- <command>
 */

import { spawn, spawnSync, execSync } from 'node:child_process'
import { existsSync, rmSync, copyFileSync, readFileSync } from 'node:fs'
import { tmpdir, platform } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { createInterface } from 'node:readline/promises'
import { stdin as input, stdout as output } from 'node:process'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root      = resolve(__dirname, '..')
const isWin     = platform() === 'win32'

// ── Colours ───────────────────────────────────────────────────────────────────
const c = {
  reset: '\x1b[0m', bold: '\x1b[1m', dim: '\x1b[2m',
  cyan: '\x1b[36m', green: '\x1b[32m', yellow: '\x1b[33m',
  red: '\x1b[31m', purple: '\x1b[35m', blue: '\x1b[34m',
}
const ok   = m => console.log(`${c.green}  ✓${c.reset} ${m}`)
const warn = m => console.log(`${c.yellow}  !${c.reset} ${m}`)
const err  = m => console.error(`${c.red}  ✗${c.reset} ${m}`)
const head = m => console.log(`\n${c.bold}${c.purple}  ${m}${c.reset}`)
const info = m => console.log(`${c.cyan}  ▸${c.reset} ${m}`)

// ── Command registry ──────────────────────────────────────────────────────────
const COMMANDS = {
  // ── Setup ──
  setup: {
    group: 'Setup',
    summary: 'Auto-install deps, create .env, pull Ollama models',
    run: setup,
  },
  install: {
    group: 'Setup',
    summary: 'Install Node and Python dependencies',
    run: install,
  },

  // ── Development ──
  dev: {
    group: 'Dev',
    summary: 'Start Vite + Electron for desktop development',
    run: () => npm(['run', 'dev', ...rest]),
  },
  'dev:lan': {
    group: 'Dev',
    summary: 'Start dev mode with Vite exposed on your LAN',
    run: () => npm(['run', 'dev:lan', ...rest]),
  },
  web: {
    group: 'Dev',
    summary: 'Start backend + browser UI without Electron',
    run: () => npm(['run', 'web', ...rest]),
  },
  'web:lan': {
    group: 'Dev',
    summary: 'Start browser UI on your LAN for phones and tablets',
    run: () => npm(['run', 'web:lan', ...rest]),
  },
  backend: {
    group: 'Dev',
    summary: 'Start only the FastAPI backend',
    run: () => python(['backend/server.py', ...rest]),
  },
  frontend: {
    group: 'Dev',
    summary: 'Start only the Vite dev server',
    run: () => npm(['run', 'dev', '--workspace=frontend', ...rest]),
  },
  electron: {
    group: 'Dev',
    summary: 'Start only the Electron shell',
    run: () => npm(['start', '--workspace=electron', ...rest]),
  },

  // ── Docker ──
  docker: {
    group: 'Docker',
    summary: 'Build + start with Docker (auto-detects CPU / GPU / cloud)',
    run: () => node(['scripts/docker.mjs', ...rest]),
  },
  'docker:gpu': {
    group: 'Docker',
    summary: 'Force GPU mode (NVIDIA)',
    run: () => node(['scripts/docker.mjs', '--gpu', ...rest]),
  },
  'docker:cloud': {
    group: 'Docker',
    summary: 'Cloud LLM mode (no Ollama)',
    run: () => node(['scripts/docker.mjs', '--cloud', ...rest]),
  },
  'docker:down': {
    group: 'Docker',
    summary: 'Stop all Docker containers',
    run: () => node(['scripts/docker.mjs', '--down']),
  },
  'docker:logs': {
    group: 'Docker',
    summary: 'Tail Docker logs for the luna container',
    run: () => node(['scripts/docker.mjs', '--logs']),
  },
  'docker:pull': {
    group: 'Docker',
    summary: 'Re-pull Ollama models (run after changing ollama_model in .env)',
    run: () => node(['scripts/docker.mjs', '--pull']),
  },

  // ── Build ──
  build: {
    group: 'Build',
    summary: 'Build the React frontend',
    run: () => npm(['run', 'build', ...rest]),
  },
  dist: {
    group: 'Build',
    summary: 'Build frontend + package Electron for Windows',
    run: () => npm(['run', 'dist', ...rest]),
  },

  // ── Diagnostics ──
  doctor: {
    group: 'Diagnostics',
    summary: 'Check Node, Python, Ollama, and Docker availability',
    run: doctor,
  },
  check: {
    group: 'Diagnostics',
    summary: 'Run backend syntax checks (py_compile)',
    run: check,
  },
  processes: {
    group: 'Diagnostics',
    summary: 'List registered background processes',
    run: () => python(['-c',
      'from backend.processes.registry import list_processes; import json; print(json.dumps(list_processes(), indent=2))',
    ]),
  },
  health: {
    group: 'Diagnostics',
    summary: 'Check if the running Luna backend is healthy',
    run: healthCheck,
  },

  // ── Docs ──
  chat: {
    group: 'Chat',
    summary: 'Interactive terminal chat with the running Luna backend',
    run: () => chatCli(rest),
  },

  docs: {
    group: 'Docs',
    summary: 'Start the docs site (Next.js dev server)',
    run: () => npm(['--prefix', 'docs-site', 'run', 'dev']),
  },

  // ── Utility ──
  clean: {
    group: 'Utility',
    summary: 'Remove build artifacts and runtime data',
    run: clean,
  },
  tunnel: {
    group: 'Utility',
    summary: 'Expose local Vite dev server via Cloudflare tunnel',
    run: () => npm(['run', 'tunnel', ...rest]),
  },
  help: {
    group: 'Utility',
    summary: 'Show this help',
    run: () => help(),
  },
}

const command = process.argv[2] ?? 'help'
const rest    = process.argv.slice(3)

if (!COMMANDS[command]) {
  err(`Unknown command: ${command}\n`)
  help(1)
} else {
  COMMANDS[command].run()
}

// ── Help ──────────────────────────────────────────────────────────────────────
function help(exitCode = 0) {
  console.log(`\n${c.bold}${c.purple}  L.U.N.A. CLI${c.reset}`)
  console.log(`  ${c.dim}Large Unified Nexus Mind AI${c.reset}\n`)
  console.log(`  ${c.bold}Usage:${c.reset}  luna <command>`)
  console.log(`          npm run luna -- <command>\n`)

  const groups = [...new Set(Object.values(COMMANDS).map(v => v.group))]
  for (const group of groups) {
    console.log(`  ${c.bold}${c.cyan}${group}${c.reset}`)
    for (const [name, meta] of Object.entries(COMMANDS)) {
      if (meta.group !== group) continue
      console.log(`    ${c.bold}${name.padEnd(16)}${c.reset}${c.dim}${meta.summary}${c.reset}`)
    }
    console.log()
  }
  process.exit(exitCode)
}

// ── Runners ───────────────────────────────────────────────────────────────────
function npm(args)  { run(isWin ? 'npm.cmd' : 'npm', args) }
function python(args) { run(isWin ? 'python' : 'python3', args) }
function node(args) { run(process.execPath, args) }

function run(bin, args) {
  const child = spawn(bin, args, {
    cwd: root,
    stdio: 'inherit',
    shell: isWin && bin.endsWith('.cmd'),
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: '1',
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
    },
  })
  child.on('exit', code => process.exit(code ?? 0))
  child.on('error', e => { err(e.message); process.exit(1) })
}

function quiet(cmd) {
  try { return execSync(cmd, { cwd: root, stdio: 'pipe' }).toString().trim() }
  catch { return '' }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
async function setup() {
  console.log(`\n${c.bold}${c.purple}  ██╗     ██╗   ██╗███╗   ██╗ █████╗ ${c.reset}`)
  console.log(`${c.bold}${c.purple}  ███████╗╚██████╔╝██║ ╚████║██║  ██║${c.reset}`)
  console.log(`  ${c.dim}Large Unified Nexus Mind AI — setup${c.reset}\n`)

  // .env
  head('Configuration...')
  const envPath = join(root, '.env')
  if (!existsSync(envPath)) {
    const ex = join(root, '.env.example')
    if (!existsSync(ex)) { err('.env.example not found.'); process.exit(1) }
    copyFileSync(ex, envPath)
    ok('Created .env from .env.example')
    warn('Edit .env — set your model name and location before running Luna.')
  } else {
    ok('.env exists')
  }

  // Node deps
  head('Installing Node dependencies...')
  runSync(isWin ? 'npm.cmd' : 'npm', ['install'])
  runSync(isWin ? 'npm.cmd' : 'npm', ['install', '--prefix', 'frontend'])
  ok('Node dependencies installed')

  // Python venv
  head('Setting up Python virtual environment...')
  const venvPath = join(root, '.venv')
  if (!existsSync(venvPath)) {
    runSync(isWin ? 'python' : 'python3', ['-m', 'venv', '.venv'])
    ok('Created .venv')
  } else {
    ok('.venv already exists')
  }

  const pip = isWin
    ? join(root, '.venv', 'Scripts', 'pip.exe')
    : join(root, '.venv', 'bin', 'pip')

  runSync(pip, ['install', '--upgrade', 'pip', '--quiet'])
  runSync(pip, ['install', '-r', 'backend/requirements.txt', '--quiet'])
  ok('Python dependencies installed')

  // Ollama models
  head('Pulling Ollama models...')
  const env = readEnvFile()
  const chatModel  = env.ollama_model       || 'qwen2.5:7b'
  const embedModel = env.ollama_embed_model || 'nomic-embed-text'

  if (quiet('ollama --version')) {
    for (const model of [chatModel, embedModel]) {
      info(`Pulling ${model}...`)
      runSync('ollama', ['pull', model])
      ok(model)
    }
  } else {
    warn('Ollama not found — install it from https://ollama.com/ and pull models manually:')
    warn(`  ollama pull ${chatModel}`)
    warn(`  ollama pull ${embedModel}`)
  }

  console.log(`\n${c.bold}${c.green}  Setup complete!${c.reset}\n`)
  console.log(`  Start Luna:  ${c.cyan}luna dev${c.reset}       (desktop with Electron)`)
  console.log(`               ${c.cyan}luna docker${c.reset}    (any device via Docker)`)
  console.log(`               ${c.cyan}luna backend${c.reset}   (API only)\n`)
}

// ── Install (deps only) ───────────────────────────────────────────────────────
function install() {
  head('Installing Node dependencies...')
  runSync(isWin ? 'npm.cmd' : 'npm', ['install'])
  runSync(isWin ? 'npm.cmd' : 'npm', ['install', '--prefix', 'frontend'])
  ok('Node done')

  const pip = isWin
    ? join(root, '.venv', 'Scripts', 'pip.exe')
    : join(root, '.venv', 'bin', 'pip')

  if (existsSync(pip)) {
    head('Installing Python dependencies...')
    runSync(pip, ['install', '-r', 'backend/requirements.txt', '--quiet'])
    ok('Python done')
  } else {
    warn('No .venv found — run: luna setup')
  }
}

// ── Health check ──────────────────────────────────────────────────────────────
async function healthCheck() {
  const env  = readEnvFile()
  const port = env.port || '8899'
  const url  = `http://localhost:${port}/api/system/health`
  info(`GET ${url}`)
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(5000) })
    const body = await r.json()
    if (r.ok) { ok(`Healthy — ${JSON.stringify(body)}`); process.exit(0) }
    else      { err(`Unhealthy ${r.status} — ${JSON.stringify(body)}`); process.exit(1) }
  } catch (e) {
    err(`Not reachable: ${e.message}`)
    process.exit(1)
  }
}

// ── Doctor ────────────────────────────────────────────────────────────────────
async function chatCli(args = []) {
  const env = readEnvFile()
  const port = env.port || '8899'
  const baseUrl = process.env.LUNA_URL || env.luna_url || `http://localhost:${port}`
  let conversationId = null
  const firstMessage = args.join(' ').trim()

  console.log(`${c.bold}
  ██╗     ██╗   ██╗███╗   ██╗ █████╗
  ██║     ██║   ██║████╗  ██║██╔══██╗
  ██║     ██║   ██║██╔██╗ ██║███████║
  ██║     ██║   ██║██║╚██╗██║██╔══██║
  ███████╗╚██████╔╝██║ ╚████║██║  ██║
  ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝
${c.reset}  Large Unified Nexus Mind AI
`)
  console.log(`  ${c.dim}${baseUrl}${c.reset}`)
  console.log(`  ${c.dim}Type /exit or press Ctrl+C to quit. Type /new for a new conversation.${c.reset}\n`)

  async function sendMessage(message) {
    const body = { message }
    if (conversationId) body.conversation_id = conversationId

    let wrote = false
    output.write(`${c.purple}Luna>${c.reset} `)

    try {
      const response = await fetch(`${baseUrl}/api/chat/stream?cli=true`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!response.ok) {
        const text = await response.text().catch(() => '')
        output.write('\n')
        err(`Chat failed ${response.status}: ${text || response.statusText}`)
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      for await (const chunk of response.body) {
        buffer += decoder.decode(chunk, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const event of events) {
          for (const line of event.split('\n')) {
            if (!line.startsWith('data:')) continue
            const raw = line.slice(5).trim()
            if (!raw) continue

            let data
            try { data = JSON.parse(raw) }
            catch { continue }

            if (data.type === 'meta' && data.conversation_id) {
              conversationId = data.conversation_id
            } else if (data.type === 'message_part' && data.content) {
              output.write(data.content)
              wrote = true
            } else if (data.type === 'confirmation_required') {
              output.write(`\n${c.yellow}Confirmation required:${c.reset} ${data.message}\n`)
            } else if (data.type === 'error') {
              output.write('\n')
              err(data.message || 'Chat stream error')
            } else if (data.type === 'done' && data.conversation_id) {
              conversationId = data.conversation_id
            }
          }
        }
      }
    } catch (e) {
      output.write('\n')
      err(`Not reachable: ${e.message}`)
      info('Start Luna first: npm run docker')
      return
    }

    output.write(wrote ? '\n\n' : '(no response)\n\n')
  }

  if (firstMessage) {
    await sendMessage(firstMessage)
    return
  }

  const rl = createInterface({ input, output })
  try {
    while (true) {
      const message = (await rl.question(`${c.cyan}You>${c.reset} `)).trim()
      if (!message) continue
      if (message === '/exit' || message === '/quit') break
      if (message === '/new') {
        conversationId = null
        ok('Started a new conversation')
        continue
      }
      await sendMessage(message)
    }
  } finally {
    rl.close()
  }
}

function doctor() {
  head('Environment check...')
  const checks = [
    ['node',   ['--version']],
    ['npm',    ['--version']],
    [isWin ? 'python' : 'python3', ['--version']],
    ['ollama', ['--version']],
    ['docker', ['--version']],
    ['git',    ['--version']],
  ]
  let i = 0
  const next = () => {
    if (i >= checks.length) return
    const [bin, args] = checks[i++]
    const r = spawnSync(bin, args, { stdio: 'pipe', shell: isWin })
    const out = (r.stdout?.toString() || r.stderr?.toString() || '').trim().split('\n')[0]
    const label = bin.replace(/\.exe$|\.cmd$/, '').padEnd(10)
    if (r.status === 0) ok(`${label} ${out}`)
    else                warn(`${label} not found`)
    next()
  }
  next()
}

// ── Check ─────────────────────────────────────────────────────────────────────
function check() {
  const cacheDir = join(tmpdir(), `luna-pycache-${process.pid}`)
  if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
  const files = [
    'backend/main.py', 'backend/server.py',
    'backend/routers/luna.py', 'backend/routers/agent.py',
    'backend/services/llm.py', 'backend/processes/registry.py',
  ]
  const child = spawn(isWin ? 'python' : 'python3',
    ['-m', 'py_compile', ...files],
    {
      cwd: root, stdio: 'inherit', shell: false,
      env: { ...process.env, PYTHONPYCACHEPREFIX: cacheDir, PYTHONIOENCODING: 'utf-8' },
    }
  )
  child.on('exit', code => {
    if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
    if (code === 0) ok('Backend syntax OK')
    process.exit(code ?? 0)
  })
  child.on('error', e => {
    if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
    err(e.message); process.exit(1)
  })
}

// ── Clean ─────────────────────────────────────────────────────────────────────
function clean() {
  const targets = ['data', 'dist', 'dist-electron', 'frontend/dist', '.pytest_cache']
  const files   = ['.env', 'run.log', 'run_err.log', 'server.log', 'server_err.log', 'cloudflared.exe']
  for (const t of [...targets, ...files]) {
    const p = join(root, t)
    if (existsSync(p)) { rmSync(p, { recursive: true, force: true }); info(`removed ${t}`) }
  }
  ok('Clean done')
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function runSync(bin, args) {
  const r = spawnSync(bin, args, {
    cwd: root, stdio: 'inherit', shell: isWin && bin.endsWith('.cmd'),
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
  })
  if (r.status !== 0) { err(`${bin} exited with code ${r.status}`); process.exit(r.status ?? 1) }
}

function readEnvFile() {
  const p = join(root, '.env')
  if (!existsSync(p)) return {}
  return Object.fromEntries(
    readFileSync(p, 'utf8').split('\n')
      .filter(l => l.includes('=') && !l.startsWith('#'))
      .map(l => { const i = l.indexOf('='); return [l.slice(0, i).trim(), l.slice(i + 1).trim()] })
  )
}
