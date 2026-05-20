#!/usr/bin/env node
import { spawn } from 'node:child_process'
import { existsSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const root = resolve(__dirname, '..')
const isWin = process.platform === 'win32'

const command = process.argv[2] ?? 'help'
const args = process.argv.slice(3)

const commands = {
  help: {
    summary: 'Show CLI help',
    run: help,
  },
  dev: {
    summary: 'Start Vite and Electron for local desktop development',
    run: () => npm(['run', 'dev', ...args]),
  },
  'dev:lan': {
    summary: 'Start development mode with Vite exposed on the LAN',
    run: () => npm(['run', 'dev:lan', ...args]),
  },
  backend: {
    summary: 'Start only the FastAPI backend',
    run: () => python(['backend/server.py', ...args]),
  },
  frontend: {
    summary: 'Start only the Vite frontend',
    run: () => npm(['run', 'dev', '--workspace=frontend', ...args]),
  },
  electron: {
    summary: 'Start only the Electron shell',
    run: () => npm(['start', '--workspace=electron', ...args]),
  },
  build: {
    summary: 'Build the frontend',
    run: () => npm(['run', 'build', ...args]),
  },
  dist: {
    summary: 'Build the frontend and Windows Electron package',
    run: () => npm(['run', 'dist', ...args]),
  },
  check: {
    summary: 'Run lightweight backend syntax checks',
    run: check,
  },
  processes: {
    summary: 'List registered backend processes',
    run: () => python(['-c', 'from backend.processes.registry import list_processes; import json; print(json.dumps(list_processes(), indent=2))']),
  },
  doctor: {
    summary: 'Check local tool availability',
    run: doctor,
  },
  clean: {
    summary: 'Remove local runtime/build artifacts ignored by git',
    run: clean,
  },
}

if (!commands[command]) {
  console.error(`Unknown command: ${command}\n`)
  help(1)
} else {
  commands[command].run()
}

function help(exitCode = 0) {
  console.log(`L.U.N.A. CLI

Usage:
  luna <command>
  npm run luna -- <command>

Commands:`)
  for (const [name, meta] of Object.entries(commands)) {
    console.log(`  ${name.padEnd(12)} ${meta.summary}`)
  }
  process.exit(exitCode)
}

function npm(npmArgs) {
  run(isWin ? 'npm.cmd' : 'npm', npmArgs)
}

function python(pyArgs) {
  run(isWin ? 'python' : 'python3', pyArgs)
}

function run(bin, binArgs) {
  runWithEnv(bin, binArgs, {})
}

function runWithEnv(bin, binArgs, extraEnv) {
  const env = buildEnv(extraEnv)
  const child = spawn(bin, binArgs, {
    cwd: root,
    stdio: 'inherit',
    shell: isWin && bin.endsWith('.cmd'),
    env,
  })
  child.on('exit', code => process.exit(code ?? 0))
  child.on('error', error => {
    console.error(error.message)
    process.exit(1)
  })
}

function buildEnv(extraEnv = {}) {
  const env = {
    ...process.env,
    ...extraEnv,
    PYTHONDONTWRITEBYTECODE: '1',
    PYTHONUNBUFFERED: '1',
    PYTHONIOENCODING: 'utf-8',
  }
  delete env.ELECTRON_RUN_AS_NODE
  return env
}

function check() {
  const cacheDir = join(tmpdir(), `luna-pycache-${process.pid}`)
  if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
  const child = spawn(isWin ? 'python' : 'python3', [
    '-m',
    'py_compile',
    'backend/main.py',
    'backend/server.py',
    'backend/routers/luna.py',
    'backend/routers/agent.py',
    'backend/services/llm.py',
    'backend/processes/registry.py',
  ], {
    cwd: root,
    stdio: 'inherit',
    shell: false,
    env: buildEnv({
      PYTHONPYCACHEPREFIX: cacheDir,
    }),
  })
  child.on('exit', code => {
    if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
    process.exit(code ?? 0)
  })
  child.on('error', error => {
    if (existsSync(cacheDir)) rmSync(cacheDir, { recursive: true, force: true })
    console.error(error.message)
    process.exit(1)
  })
}

function doctor() {
  const checks = [
    [isWin ? 'node.exe' : 'node', ['--version']],
    [isWin ? 'npm.cmd' : 'npm', ['--version']],
    [isWin ? 'python' : 'python3', ['--version']],
  ]
  let index = 0
  const next = () => {
    if (index >= checks.length) return
    const [bin, binArgs] = checks[index++]
    const child = spawn(bin, binArgs, { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], shell: isWin && bin.endsWith('.cmd') })
    let output = ''
    child.stdout.on('data', chunk => { output += chunk.toString() })
    child.stderr.on('data', chunk => { output += chunk.toString() })
    child.on('close', code => {
      const name = bin.replace(/\.cmd$|\.exe$/, '')
      if (code === 0) {
        console.log(`${name.padEnd(8)} ${output.trim()}`)
      } else {
        console.log(`${name.padEnd(8)} missing or unavailable`)
      }
      next()
    })
    child.on('error', () => {
      const name = bin.replace(/\.cmd$|\.exe$/, '')
      console.log(`${name.padEnd(8)} missing or unavailable`)
      next()
    })
  }
  next()
}

function clean() {
  const targets = [
    'data',
    'dist',
    'dist-electron',
    'frontend/dist',
    '.pytest_cache',
  ]
  const files = [
    '.env',
    'run.log',
    'run_err.log',
    'server.log',
    'server_err.log',
    'cloudflared.exe',
  ]
  for (const target of [...targets, ...files]) {
    const full = join(root, target)
    if (existsSync(full)) {
      rmSync(full, { recursive: true, force: true })
      console.log(`removed ${target}`)
    }
  }
}
