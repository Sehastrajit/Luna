"""
Luna benchmark runner -- production-grade, hardware/provider agnostic.

Works with any Luna-supported LLM provider (Ollama, OpenAI-compatible,
Anthropic, Google, Groq, Cohere, Mistral) and any accelerator
(NVIDIA, AMD, Apple Silicon, CPU-only).

Suites
------
llm      -- TTFT, sustained throughput, statistical distribution
memory   -- retrieval hit-rate and latency (skips quality if DB empty)
tools    -- safe tool execution success-rate and latency

Statistics
----------
Every probe runs --runs times (default 3). Reports mean, stddev, p50, p95.
First call is separately labeled "cold"; remaining calls are "warm" aggregate.

Usage
-----
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --suite llm --runs 5
    python scripts/run_benchmark.py --suite llm,tools --output docs/BENCHMARKS.md
    python scripts/run_benchmark.py --json results/bench.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ── Early arg parse so --provider can set env vars before settings loads ──────
# (pydantic-settings reads os.environ at instantiation time)
import os as _os
_pre = argparse.ArgumentParser(add_help=False)
_pre.add_argument("--provider", default=None)
_pre.add_argument("--model",    default=None)
_pre.add_argument("--api-key",  default=None, dest="api_key")
_known, _ = _pre.parse_known_args()
if _known.provider:
    _os.environ["LLM_PROVIDER"] = _known.provider
if _known.model:
    _os.environ[f"{_known.provider.upper().replace('-','_')}_MODEL"] = _known.model
if _known.api_key:
    _os.environ[f"{(_known.provider or 'openai').upper().replace('-','_')}_API_KEY"] = _known.api_key

from backend.config import settings
from backend.models.database import init_db, SessionLocal
from backend.services.llm import LLMClient
from backend.services.memory_manager import MemoryManager


# ── Statistics ────────────────────────────────────────────────────────────────

@dataclass
class Stats:
    n:      int
    mean:   float
    stddev: float
    p50:    float
    p95:    float
    min:    float
    max:    float

    def __str__(self) -> str:
        return f"{self.mean:.0f} ms  (stddev {self.stddev:.0f}  p50 {self.p50:.0f}  p95 {self.p95:.0f})"


def compute_stats(values: list[float]) -> Optional[Stats]:
    if not values:
        return None
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / n
    stddev = math.sqrt(variance)
    sv = sorted(values)
    def pct(p: int) -> float:
        return sv[min(int(n * p / 100), n - 1)]
    return Stats(n=n, mean=round(mean, 1), stddev=round(stddev, 1),
                 p50=round(pct(50), 1), p95=round(pct(95), 1),
                 min=round(min(values), 1), max=round(max(values), 1))


# ── Hardware detection ────────────────────────────────────────────────────────

@dataclass
class HardwareInfo:
    accelerator: str = "unknown"
    accel_vendor: str = ""
    accel_mem_mb: int = 0
    accel_mem_used_mb: int = 0
    accel_temp_c: str = ""
    accel_driver: str = ""
    cpu: str = ""
    ram_gb: float = 0.0
    os: str = ""


def _detect_nvidia() -> Optional[dict]:
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,temperature.gpu,driver_version",
             "--format=csv,noheader,nounits"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip().split("\n")[0]
        p = [x.strip() for x in out.split(",")]
        return {
            "accelerator":      p[0],
            "accel_vendor":     "NVIDIA",
            "accel_mem_mb":     int(p[1]),
            "accel_mem_used_mb":int(p[2]),
            "accel_temp_c":     p[3] + " C",
            "accel_driver":     p[4],
        }
    except Exception:
        return None


def _detect_amd() -> Optional[dict]:
    try:
        out = subprocess.check_output(
            ["rocm-smi", "--showproductname", "--showmeminfo", "vram", "--csv"],
            text=True, stderr=subprocess.DEVNULL,
        )
        return {"accelerator": "AMD GPU", "accel_vendor": "AMD", "accel_mem_mb": 0}
    except Exception:
        return None


def _detect_apple() -> Optional[dict]:
    try:
        import platform as _p
        if _p.system() != "Darwin":
            return None
        out = subprocess.check_output(
            ["system_profiler", "SPHardwareDataType"], text=True
        )
        if "Apple" in out and ("M1" in out or "M2" in out or "M3" in out or "M4" in out):
            chip = next((l.split(":")[1].strip() for l in out.splitlines() if "Chip" in l), "Apple Silicon")
            mem = next((l.split(":")[1].strip() for l in out.splitlines() if "Memory" in l), "")
            return {"accelerator": chip, "accel_vendor": "Apple", "accel_mem_mb": 0, "accel_note": mem}
    except Exception:
        pass
    return None


def _cpu_ram() -> tuple[str, float]:
    cpu = platform.processor() or platform.machine()
    try:
        import psutil
        ram = round(psutil.virtual_memory().total / 1024 ** 3, 1)
    except Exception:
        ram = 0.0
    return cpu, ram


def detect_hardware() -> HardwareInfo:
    hw = HardwareInfo()
    hw.os = f"{platform.system()} {platform.release()}"
    hw.cpu, hw.ram_gb = _cpu_ram()

    gpu = _detect_nvidia() or _detect_amd() or _detect_apple()
    if gpu:
        for k, v in gpu.items():
            if hasattr(hw, k):
                setattr(hw, k, v)
    else:
        hw.accelerator = "CPU only"
        hw.accel_vendor = "CPU"

    return hw


# ── Model info ────────────────────────────────────────────────────────────────

def get_model_label() -> str:
    """Return a human-readable model identifier for any configured provider."""
    p = settings.llm_provider.lower()
    if p == "ollama":
        return settings.ollama_model
    if p in ("openai-compatible", "nvidia-nim"):
        return getattr(settings, "openai_compatible_model", "openai-compatible")
    if p == "anthropic":
        return getattr(settings, "anthropic_model", "claude")
    if p == "google":
        return getattr(settings, "google_model", "gemini")
    if p == "groq":
        return getattr(settings, "groq_model", "groq")
    if p == "cohere":
        return getattr(settings, "cohere_model", "command-r")
    if p == "mistral":
        return getattr(settings, "mistral_model", "mistral")
    return p


# ── LLM suite ─────────────────────────────────────────────────────────────────

# (label, prompt, min_output_chars, is_long_form)
# is_long_form=True → this prompt is used for throughput (tok/s) reporting
LLM_PROBES = [
    ("echo",        "Reply with exactly one word: pong",                              3,  False),
    ("arithmetic",  "What is 17 times 13? Answer with the number only.",              2,  False),
    ("short-list",  "Name 5 continents. One per line, no other text.",               20,  False),
    ("medium",      "Write exactly 5 bullet points about running AI models locally.", 80,  True),
    ("long",        "Explain transformer attention in 4 sentences.",                  120, True),
]

WARMUP_PROMPT = "Say hi."


async def _single_llm_call(llm: LLMClient, prompt: str) -> tuple[float, float, str]:
    """Returns (ttft_ms, total_ms, full_output)."""
    t0   = time.perf_counter()
    ttft = None
    out  = ""
    async for chunk in llm.stream_chat([{"role": "user", "content": prompt}], ""):
        if ttft is None and chunk.strip():
            ttft = (time.perf_counter() - t0) * 1000
        out += chunk
    total = (time.perf_counter() - t0) * 1000
    return ttft or total, total, out


async def bench_llm(llm: LLMClient, runs: int = 3) -> dict:
    print(f"\n  Warming up ({WARMUP_PROMPT!r}) x2 ...", end=" ", flush=True)
    for _ in range(2):
        try:
            async for _ in llm.stream_chat([{"role": "user", "content": WARMUP_PROMPT}], ""):
                break
        except Exception:
            pass
    print("done")

    all_ttfts, all_totals = [], []
    long_tps: list[float] = []
    probe_results = []

    for label, prompt, min_chars, is_long in LLM_PROBES:
        print(f"  [{label}]", end=" ", flush=True)
        run_ttfts, run_totals, run_tps = [], [], []
        first_ok = True

        for i in range(runs):
            tag = "[cold]" if i == 0 else f"[{i+1}]"
            try:
                ttft, total, out = await _single_llm_call(llm, prompt)
                ok = len(out) >= min_chars
                out_tokens = max(1, len(out) // 4)
                tps = out_tokens / (total / 1000)

                run_ttfts.append(ttft)
                run_totals.append(total)
                if is_long:
                    run_tps.append(tps)

                flag = "ok" if ok else "SHORT"
                print(f"{tag} ttft={ttft:.0f}ms total={total:.0f}ms", end=" ", flush=True)
                if is_long:
                    print(f"~{tps:.0f}tok/s", end=" ", flush=True)
                print(f"[{flag}]", end="  ", flush=True)
                first_ok = ok
            except Exception as exc:
                print(f"{tag} ERROR:{exc}", end="  ", flush=True)

        print()

        cold_ttft = run_ttfts[0] if run_ttfts else None
        warm_ttfts = run_ttfts[1:]
        ttft_stats = compute_stats(warm_ttfts) if warm_ttfts else compute_stats(run_ttfts)
        total_stats = compute_stats(run_totals[1:] if len(run_totals) > 1 else run_totals)
        tps_stats   = compute_stats(run_tps) if run_tps else None

        all_ttfts.extend(warm_ttfts or run_ttfts)
        all_totals.extend(run_totals[1:] if len(run_totals) > 1 else run_totals)
        if run_tps:
            long_tps.extend(run_tps)

        probe_results.append({
            "label":        label,
            "cold_ttft_ms": round(cold_ttft) if cold_ttft else None,
            "ttft_ms":      asdict(ttft_stats)  if ttft_stats  else None,
            "total_ms":     asdict(total_stats) if total_stats else None,
            "tok_s":        asdict(tps_stats)   if tps_stats   else None,
            "is_long_form": is_long,
        })

    overall_ttft  = compute_stats(all_ttfts)
    overall_total = compute_stats(all_totals)
    throughput    = compute_stats(long_tps)

    return {
        "model":          get_model_label(),
        "provider":       settings.llm_provider,
        "runs_per_probe": runs,
        "ttft":           asdict(overall_ttft)  if overall_ttft  else None,
        "total":          asdict(overall_total) if overall_total else None,
        "throughput_toks":asdict(throughput)    if throughput    else None,
        "probes":         probe_results,
    }


# ── Memory suite ──────────────────────────────────────────────────────────────

MEMORY_PROBES = [
    ("my name",        ["personal", "identity", "name"]),
    ("my job",         ["work", "job", "career", "study"]),
    ("my hobbies",     ["hobby", "interest", "activity", "sport"]),
    ("where I live",   ["location", "home", "city", "country"]),
    ("food preference",["food", "diet", "preference"]),
    ("close contacts", ["relationship", "friend", "family"]),
]

MIN_FACTS_FOR_QUALITY = 10   # below this, only latency is meaningful


async def bench_memory(db, runs: int = 3) -> dict:
    from sqlalchemy import text
    total_facts = db.execute(text("SELECT COUNT(*) FROM facts WHERE is_active=1")).scalar()
    print(f"  Facts in DB: {total_facts}", end="")
    if total_facts < MIN_FACTS_FOR_QUALITY:
        print(f"  (< {MIN_FACTS_FOR_QUALITY} -- quality metrics skipped, latency only)")
    else:
        print()

    mm = MemoryManager(db)
    latencies: list[float] = []
    hits = 0
    results = []

    for query_label, cats in MEMORY_PROBES:
        query = f"Tell me about {query_label}."
        print(f"  [{query_label[:20]}]", end=" ", flush=True)
        run_lats = []

        for i in range(runs):
            t0 = time.perf_counter()
            try:
                facts = await mm.retrieve_relevant(query)
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                n_hits = len(facts) if isinstance(facts, list) else 0
                print(f"[{i+1}] {lat:.0f}ms hits={n_hits}", end="  ", flush=True)
                if i == 0 and n_hits > 0:
                    hits += 1
            except Exception as exc:
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                print(f"[{i+1}] ERR {lat:.0f}ms", end="  ", flush=True)

        print()
        latencies.extend(run_lats)
        lat_stats = compute_stats(run_lats)
        results.append({
            "query": query_label,
            "latency_ms": asdict(lat_stats) if lat_stats else None,
        })

    lat_stats_all = compute_stats(latencies)
    return {
        "total_facts":    total_facts,
        "quality_valid":  total_facts >= MIN_FACTS_FOR_QUALITY,
        "hit_rate":       round(hits / len(MEMORY_PROBES), 3) if total_facts >= MIN_FACTS_FOR_QUALITY else None,
        "latency_ms":     asdict(lat_stats_all) if lat_stats_all else None,
        "probes":         results,
        "note":           f"Re-run after {MIN_FACTS_FOR_QUALITY}+ conversations for quality metrics." if total_facts < MIN_FACTS_FOR_QUALITY else "",
    }


# ── Tools suite ───────────────────────────────────────────────────────────────

# (name, sync_fn_or_async_fn, is_async, required_setting_or_None)
def _tool_probes() -> list[tuple[str, Any, bool, Optional[str]]]:
    from backend.services import workspace, web_tools
    probes = [
        ("workspace_list", lambda: workspace.list_workspace(""),             False, None),
        ("web_search",     lambda: web_tools.web_search("Luna AI engine"),   True,  None),
    ]
    return probes


async def bench_tools(runs: int = 3) -> dict:
    probes = _tool_probes()
    tool_results = []

    for name, fn, is_async, req_setting in probes:
        if req_setting and not getattr(settings, req_setting, None):
            print(f"  [{name}] SKIP (requires {req_setting})")
            continue

        print(f"  [{name}]", end=" ", flush=True)
        run_lats: list[float] = []
        successes = 0

        for i in range(runs):
            t0 = time.perf_counter()
            try:
                result = await fn() if is_async else fn()
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                ok = bool(result)
                if ok:
                    successes += 1
                print(f"[{i+1}] {lat:.0f}ms {'ok' if ok else 'empty'}", end="  ", flush=True)
            except Exception as exc:
                lat = (time.perf_counter() - t0) * 1000
                run_lats.append(lat)
                print(f"[{i+1}] {lat:.0f}ms ERR:{str(exc)[:40]}", end="  ", flush=True)

        print()
        lat_stats = compute_stats(run_lats)
        tool_results.append({
            "tool":         name,
            "success_rate": round(successes / runs, 3),
            "latency_ms":   asdict(lat_stats) if lat_stats else None,
        })

    overall_sr = (
        round(sum(r["success_rate"] for r in tool_results) / len(tool_results), 3)
        if tool_results else 0.0
    )
    return {
        "probes":       tool_results,
        "success_rate": overall_sr,
    }


# ── Regression check ──────────────────────────────────────────────────────────

REGRESSION_THRESHOLD = 0.25   # flag if metric worsens by more than 25%

def check_regression(current: dict, db) -> list[str]:
    """Compare current results against last DB run. Return list of warning strings."""
    from sqlalchemy import text
    warnings: list[str] = []
    for suite in ("llm", "memory", "tools"):
        row = db.execute(
            text("SELECT metrics FROM benchmark_results WHERE suite=:s ORDER BY timestamp DESC LIMIT 1 OFFSET 1"),
            {"s": suite},
        ).fetchone()
        if not row:
            continue
        try:
            prev = json.loads(row[0])
        except Exception:
            continue

        cur_suite = current.get(suite, {})
        checks = []
        if suite == "llm":
            prev_ttft = (prev.get("ttft") or {}).get("mean")
            cur_ttft  = (cur_suite.get("ttft") or {}).get("mean")
            if prev_ttft and cur_ttft:
                checks.append(("TTFT mean", prev_ttft, cur_ttft, True))   # True=higher is worse
            prev_tps = (prev.get("throughput_toks") or {}).get("mean")
            cur_tps  = (cur_suite.get("throughput_toks") or {}).get("mean")
            if prev_tps and cur_tps:
                checks.append(("throughput", prev_tps, cur_tps, False))   # False=lower is worse
        elif suite == "memory":
            prev_lat = (prev.get("latency_ms") or {}).get("mean")
            cur_lat  = (cur_suite.get("latency_ms") or {}).get("mean")
            if prev_lat and cur_lat:
                checks.append(("retrieval latency", prev_lat, cur_lat, True))
        elif suite == "tools":
            prev_sr = prev.get("success_rate")
            cur_sr  = cur_suite.get("success_rate")
            if prev_sr is not None and cur_sr is not None:
                checks.append(("tool success rate", prev_sr, cur_sr, False))

        for name, prev_v, cur_v, higher_is_worse in checks:
            delta = (cur_v - prev_v) / max(abs(prev_v), 1e-9)
            regressed = delta > REGRESSION_THRESHOLD if higher_is_worse else delta < -REGRESSION_THRESHOLD
            if regressed:
                direction = "+" if delta > 0 else ""
                warnings.append(f"[{suite}] {name} regressed {direction}{delta*100:.0f}%  ({prev_v:.1f} -> {cur_v:.1f})")

    return warnings


# ── Persistence ───────────────────────────────────────────────────────────────

def _save(db, suite: str, metrics: dict) -> None:
    from sqlalchemy import text
    try:
        db.execute(
            text("INSERT INTO benchmark_results (suite, timestamp, metrics, errors, duration_s) "
                 "VALUES (:s, :t, :m, :e, :d)"),
            {"s": suite, "t": time.time(), "m": json.dumps(metrics, default=str),
             "e": "[]", "d": 0},
        )
        db.commit()
    except Exception as exc:
        print(f"  [DB save error: {exc}]")


# ── Markdown output ───────────────────────────────────────────────────────────

def _fmt_stats(s: Optional[dict], unit: str = "ms") -> str:
    if not s:
        return "N/A"
    return f"{s['mean']:.0f} {unit}  (p50 {s['p50']:.0f}  p95 {s['p95']:.0f}  sd {s['stddev']:.0f})"


def _fmt_stats_short(s: Optional[dict], unit: str = "ms") -> str:
    if not s:
        return "N/A"
    return f"{s['mean']:.0f} {unit}"


def render_markdown(hw: HardwareInfo, ts: str, runs: int,
                    llm_r: dict, mem_r: dict, tool_r: dict,
                    warnings: list[str]) -> str:
    lines: list[str] = []

    # Header
    lines += [
        "# Luna Benchmark Results",
        "",
        f"> **Run:** {ts}  ",
        f"> **Hardware:** {hw.accelerator}  {hw.accel_mem_mb} MB VRAM  (driver {hw.accel_driver})  ",
        f"> **CPU:** {hw.cpu}  {hw.ram_gb} GB RAM  ",
        f"> **OS:** {hw.os}  ",
        f"> **Model:** `{llm_r['model']}`  provider: `{llm_r['provider']}`  ",
        f"> **Runs per probe:** {runs}  (cold call reported separately; warm stats exclude it)",
        "",
    ]

    # Regressions
    if warnings:
        lines += ["## Regressions vs previous run", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    # TL;DR summary table
    ttft_s   = llm_r.get("ttft")
    total_s  = llm_r.get("total")
    tps_s    = llm_r.get("throughput_toks")
    mem_lat  = mem_r.get("latency_ms")

    lines += [
        "## Summary",
        "",
        "| Metric | Value | Notes |",
        "|--------|-------|-------|",
        f"| LLM TTFT (warm, p50) | **{_fmt_stats_short(ttft_s)}** | first token latency |",
        f"| LLM TTFT (warm, p95) | {ttft_s['p95'] if ttft_s else 'N/A'} ms | tail latency |",
        f"| Sustained throughput | **{_fmt_stats_short(tps_s, 'tok/s')}** | long-form prompts only |",
        f"| Memory retrieval p50 | {_fmt_stats_short(mem_lat)} | ChromaDB vector search |",
        f"| Tool success rate    | {tool_r.get('success_rate', 0)*100:.0f}% | safe tools only |",
        "",
    ]

    # LLM detail
    lines += [
        "## LLM Latency",
        "",
        "> Throughput (tok/s) is only reported for long-form prompts (50+ output tokens).",
        "> Short prompts measure TTFT responsiveness, not decode speed.",
        "",
        "### Distribution (warm calls, all probes)",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| TTFT mean | {_fmt_stats(ttft_s)} |",
        f"| Total mean | {_fmt_stats(total_s)} |",
        f"| Throughput | {_fmt_stats(tps_s, 'tok/s')} |",
        "",
        "### Per-prompt",
        "",
        "| Probe | Cold TTFT | Warm TTFT (mean) | Warm Total (mean) | tok/s |",
        "|-------|-----------|------------------|-------------------|-------|",
    ]
    for p in llm_r.get("probes", []):
        cold = f"{p['cold_ttft_ms']} ms" if p.get("cold_ttft_ms") else "N/A"
        warm = _fmt_stats_short(p.get("ttft_ms"))
        tot  = _fmt_stats_short(p.get("total_ms"))
        tps  = _fmt_stats_short(p.get("tok_s"), "tok/s") if p.get("tok_s") else "N/A (short)"
        lines.append(f"| {p['label']} | {cold} | {warm} | {tot} | {tps} |")

    # Memory detail
    lines += [
        "",
        "## Memory Retrieval",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Facts in DB | {mem_r['total_facts']} |",
    ]
    if mem_r.get("quality_valid"):
        lines.append(f"| Hit rate | {mem_r.get('hit_rate', 0)*100:.0f}% |")
    else:
        lines.append("| Hit rate | N/A (< 10 facts) |")
    lines += [
        f"| Retrieval latency | {_fmt_stats(mem_r.get('latency_ms'))} |",
    ]
    if mem_r.get("note"):
        lines += ["", f"> {mem_r['note']}"]

    # Tools detail
    lines += [
        "",
        "## Tool Execution",
        "",
        f"**Overall success rate:** {tool_r.get('success_rate', 0)*100:.0f}%",
        "",
        "| Tool | Success Rate | Latency (mean) | p95 |",
        "|------|-------------|----------------|-----|",
    ]
    for r in tool_r.get("probes", []):
        lat = r.get("latency_ms") or {}
        lines.append(
            f"| {r['tool']} | {r['success_rate']*100:.0f}% "
            f"| {lat.get('mean', 0):.0f} ms | {lat.get('p95', 0):.0f} ms |"
        )

    # System
    lines += [
        "",
        "## System",
        "",
        "| | |",
        "|---|---|",
        f"| Accelerator | {hw.accelerator} |",
        f"| VRAM total | {hw.accel_mem_mb} MB |",
        f"| VRAM used (at run) | {hw.accel_mem_used_mb} MB |",
        f"| Temperature | {hw.accel_temp_c} |",
        f"| Driver | {hw.accel_driver} |",
        f"| CPU | {hw.cpu} |",
        f"| RAM | {hw.ram_gb} GB |",
        f"| OS | {hw.os} |",
        f"| Model | `{llm_r['model']}` |",
        f"| Provider | {llm_r['provider']} |",
        "",
        "---",
        "",
        "## Rerunning",
        "",
        "```bash",
        "python scripts/run_benchmark.py",
        "python scripts/run_benchmark.py --suite llm --runs 5",
        "```",
    ]
    return "\n".join(lines) + "\n"


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Luna benchmark runner")
    p.add_argument("--suite",    default="all",
                   help="Comma-separated suites: llm,memory,tools  or  all")
    p.add_argument("--runs",     type=int, default=3,
                   help="Runs per probe (default 3, max 10)")
    p.add_argument("--output",   default=str(ROOT / "docs" / "BENCHMARKS.md"),
                   help="Markdown output path")
    p.add_argument("--json",     default=None,
                   help="Optional JSON output path")
    p.add_argument("--no-db",    action="store_true",
                   help="Skip persisting results to the Luna DB")
    p.add_argument("--provider", default=None,
                   help="Override LLM provider (e.g. groq, anthropic, ollama)")
    p.add_argument("--model",    default=None,
                   help="Override model name for the chosen provider")
    p.add_argument("--api-key",  default=None, dest="api_key",
                   help="Override API key for the chosen provider")
    return p.parse_args()


async def main() -> None:
    args   = parse_args()
    runs   = max(1, min(10, args.runs))
    suites = [s.strip() for s in args.suite.split(",")] if args.suite != "all" else ["llm", "memory", "tools"]

    init_db()
    db  = SessionLocal()
    llm = LLMClient()
    hw  = detect_hardware()
    ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sep = "-" * 60

    print(sep)
    print(f"  Luna Benchmark  --  {ts}")
    print(sep)
    print(f"  Accelerator : {hw.accelerator}  {hw.accel_mem_mb} MB  {hw.accel_temp_c}")
    print(f"  CPU / RAM   : {hw.cpu}  /  {hw.ram_gb} GB")
    print(f"  Model       : {get_model_label()}  [{settings.llm_provider}]")
    print(f"  Suites      : {', '.join(suites)}  x{runs} runs each")
    print(sep)

    results: dict[str, dict] = {}

    if "llm" in suites:
        print(f"\n[LLM]")
        t0 = time.perf_counter()
        results["llm"] = await bench_llm(llm, runs=runs)
        results["llm"]["_duration_s"] = round(time.perf_counter() - t0, 1)
        if not args.no_db:
            _save(db, "llm", results["llm"])

    if "memory" in suites:
        print(f"\n[Memory]")
        t0 = time.perf_counter()
        results["memory"] = await bench_memory(db, runs=runs)
        results["memory"]["_duration_s"] = round(time.perf_counter() - t0, 1)
        if not args.no_db:
            _save(db, "memory", results["memory"])

    if "tools" in suites:
        print(f"\n[Tools]")
        t0 = time.perf_counter()
        results["tools"] = await bench_tools(runs=runs)
        results["tools"]["_duration_s"] = round(time.perf_counter() - t0, 1)
        if not args.no_db:
            _save(db, "tools", results["tools"])

    # Regression check
    warnings = check_regression(results, db)

    # Console summary
    print(f"\n{sep}")
    print("  SUMMARY")
    print(sep)
    if "llm" in results:
        r = results["llm"]
        ttft = (r.get("ttft") or {}).get("mean", 0)
        tps  = (r.get("throughput_toks") or {}).get("mean", 0)
        print(f"  LLM TTFT (warm mean)   : {ttft:.0f} ms")
        print(f"  LLM throughput (mean)  : {tps:.1f} tok/s")
    if "memory" in results:
        r = results["memory"]
        lat = (r.get("latency_ms") or {}).get("mean", 0)
        print(f"  Memory retrieval mean  : {lat:.0f} ms  ({r.get('total_facts',0)} facts)")
    if "tools" in results:
        print(f"  Tool success rate      : {results['tools'].get('success_rate',0)*100:.0f}%")
    if warnings:
        print()
        for w in warnings:
            print(f"  WARN  {w}")
    print(sep)

    # Markdown
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    llm_r  = results.get("llm",    {"model": get_model_label(), "provider": settings.llm_provider, "probes": []})
    mem_r  = results.get("memory", {"total_facts": 0, "latency_ms": None, "probes": []})
    tool_r = results.get("tools",  {"probes": [], "success_rate": 0})
    md = render_markdown(hw, ts, runs, llm_r, mem_r, tool_r, warnings)
    out_path.write_text(md, encoding="utf-8")
    print(f"\n  Markdown -> {out_path}")

    # JSON
    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps({"timestamp": ts, "hardware": asdict(hw), "results": results}, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"  JSON     -> {json_path}")

    db.close()


if __name__ == "__main__":
    asyncio.run(main())
