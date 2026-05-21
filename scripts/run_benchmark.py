"""
Luna benchmark runner -- standalone (no FastAPI server needed).

Runs: LLM latency, memory retrieval, tool execution.
Saves results to backend DB + docs/BENCHMARKS.md.

Usage:
    cd e:/Luna
    python scripts/run_benchmark.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

# ── Project root on path ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import settings
from backend.models.database import init_db, SessionLocal
from backend.services.llm import LLMClient
from backend.services.memory_manager import MemoryManager

# ── GPU info (nvidia-smi) ─────────────────────────────────────────────────────
def _gpu_info() -> dict:
    try:
        import subprocess
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,temperature.gpu,clocks.current.sm,driver_version",
             "--format=csv,noheader"],
            text=True,
        ).strip()
        parts = [p.strip() for p in out.split(",")]
        return {
            "name":        parts[0],
            "vram_total":  parts[1],
            "vram_used":   parts[2],
            "temp_c":      parts[3],
            "sm_clock":    parts[4],
            "driver":      parts[5],
        }
    except Exception:
        return {}

def _pct(lst: list[float], p: int) -> float:
    if not lst:
        return 0.0
    s = sorted(lst)
    return s[min(int(len(s) * p / 100), len(s) - 1)]

# ── LLM benchmark ─────────────────────────────────────────────────────────────
LLM_PROBES = [
    # (label, prompt, expected_min_chars)
    ("short-echo",   "Reply with exactly this word: pong",                           3),
    ("short-math",   "What is 144 divided by 12? Answer with just the number.",      1),
    ("short-list",   "Name 3 planets, comma-separated, no other text.",              10),
    ("medium-bullets","List exactly 3 bullet points about running LLMs locally.",    60),
    ("medium-explain","Explain what a knowledge graph is in exactly two sentences.", 80),
]

async def bench_llm(llm: LLMClient) -> dict:
    print("\n[LLM] Warming up...", end=" ", flush=True)
    # Warm-up (model may be freshly loaded)
    try:
        async for _ in llm.stream_chat([{"role":"user","content":"hi"}], ""):
            break
    except Exception:
        pass
    print("done")

    ttfts, totals, tps_list, results = [], [], [], []

    for label, prompt, min_chars in LLM_PROBES:
        print(f"  [{label}] ", end="", flush=True)
        t0 = time.perf_counter()
        ttft = None
        full = ""
        try:
            async for chunk in llm.stream_chat([{"role":"user","content":prompt}], ""):
                if ttft is None and chunk.strip():
                    ttft = (time.perf_counter() - t0) * 1000
                full += chunk
            total_ms = (time.perf_counter() - t0) * 1000
            out_tokens = max(1, len(full) // 4)   # rough estimate
            tps = out_tokens / (total_ms / 1000)

            if ttft:  ttfts.append(ttft)
            totals.append(total_ms)
            tps_list.append(tps)

            status = "OK" if len(full) >= min_chars else "SHORT"
            print(f"TTFT {ttft:.0f}ms  total {total_ms:.0f}ms  ~{tps:.1f} tok/s  [{status}]")
            results.append({
                "label":    label,
                "ttft_ms":  round(ttft or 0),
                "total_ms": round(total_ms),
                "tok_s":    round(tps, 1),
                "chars_out":len(full),
                "ok":       len(full) >= min_chars,
            })
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append({"label": label, "error": str(exc)})

    return {
        "model":        settings.ollama_model,
        "provider":     settings.llm_provider,
        "ttft_p50_ms":  round(_pct(ttfts,  50)),
        "ttft_p95_ms":  round(_pct(ttfts,  95)),
        "total_p50_ms": round(_pct(totals, 50)),
        "total_p95_ms": round(_pct(totals, 95)),
        "tok_s_avg":    round(sum(tps_list) / len(tps_list), 1) if tps_list else 0,
        "tok_s_peak":   round(max(tps_list), 1) if tps_list else 0,
        "probes":       results,
    }

# ── Memory benchmark ──────────────────────────────────────────────────────────
MEMORY_PROBES = [
    ("What is my name?",           ["personal","identity","name"]),
    ("Where do I work?",           ["work","job","career"]),
    ("What are my hobbies?",       ["hobby","interest","activity"]),
    ("Where do I live?",           ["location","home","city"]),
    ("What do I like to eat?",     ["food","diet","preference"]),
    ("Who are my close contacts?", ["relationship","friend","family"]),
]

async def bench_memory(db) -> dict:
    mm = MemoryManager(db)
    hits, cat_hits, latencies, results = 0, 0, [], []

    for query, cats in MEMORY_PROBES:
        print(f"  [{query[:30]}] ", end="", flush=True)
        t0 = time.perf_counter()
        try:
            facts = await mm.retrieve_relevant(query)
            lat = (time.perf_counter() - t0) * 1000
            latencies.append(lat)
            # retrieve_relevant may return list[dict] or list[str] depending on version
            n_hits = len(facts) if isinstance(facts, list) else 0
            found = n_hits > 0
            if found:
                hits += 1
                all_cats = " ".join(
                    str(f.get("category","") if isinstance(f, dict) else "").lower()
                    for f in facts
                )
                if any(k in all_cats for k in cats):
                    cat_hits += 1
            print(f"{lat:.1f}ms  hits={n_hits}  {'OK' if found else 'MISS'}")
            results.append({"query": query, "hits": n_hits, "latency_ms": round(lat, 1)})
        except Exception as exc:
            lat = (time.perf_counter() - t0) * 1000
            latencies.append(lat)
            print(f"ERROR: {exc}")
            results.append({"query": query, "error": str(exc)})

    n = len(MEMORY_PROBES)
    # Check DB fact count for context
    from sqlalchemy import text
    total_facts = db.execute(text("SELECT COUNT(*) FROM facts WHERE is_active=1")).scalar()

    return {
        "total_facts_in_db": total_facts,
        "probes":            n,
        "hit_rate":          round(hits / n, 3),
        "category_precision":round(cat_hits / max(hits, 1), 3),
        "p50_ms":            round(_pct(latencies, 50), 1),
        "p95_ms":            round(_pct(latencies, 95), 1),
        "note":              "hit_rate=0 expected — no facts stored yet" if total_facts == 0 else "",
        "results":           results,
    }

# ── Tool benchmark ────────────────────────────────────────────────────────────
async def bench_tools() -> dict:
    from backend.services import workspace, web_tools

    probes = [
        ("workspace_list", lambda: workspace.list_workspace(""), False),
        ("web_search",     lambda: web_tools.web_search("Luna AI personal assistant"),  True),
    ]

    results = []
    for name, fn, is_async in probes:
        print(f"  [{name}] ", end="", flush=True)
        t0 = time.perf_counter()
        try:
            result = await fn() if is_async else fn()
            lat = (time.perf_counter() - t0) * 1000
            ok = bool(result)
            print(f"{lat:.0f}ms  {'OK' if ok else 'EMPTY'}")
            results.append({"tool": name, "ok": ok, "latency_ms": round(lat)})
        except Exception as exc:
            lat = (time.perf_counter() - t0) * 1000
            print(f"ERROR {lat:.0f}ms  {exc}")
            results.append({"tool": name, "ok": False, "latency_ms": round(lat), "error": str(exc)})

    successes = sum(1 for r in results if r.get("ok"))
    latencies  = [r["latency_ms"] for r in results]
    return {
        "probes":       len(results),
        "success_rate": round(successes / max(len(results), 1), 3),
        "p50_ms":       round(_pct(latencies, 50)),
        "results":      results,
    }

# ── Persist to DB ─────────────────────────────────────────────────────────────
def _save(db, suite: str, metrics: dict, errors: list, duration_s: float):
    from sqlalchemy import text
    try:
        db.execute(
            text("INSERT INTO benchmark_results (suite, timestamp, metrics, errors, duration_s) "
                 "VALUES (:s, :t, :m, :e, :d)"),
            {"s": suite, "t": time.time(), "m": json.dumps(metrics),
             "e": json.dumps(errors), "d": duration_s},
        )
        db.commit()
    except Exception as exc:
        print(f"  [DB save failed: {exc}]")

# ── Markdown report ───────────────────────────────────────────────────────────
def _markdown(gpu: dict, ts: str, llm_r: dict, mem_r: dict, tool_r: dict) -> str:
    model_short = llm_r["model"].split("/")[-1] if "/" in llm_r["model"] else llm_r["model"]
    lines = [
        "# Luna Benchmark Results",
        "",
        f"> Last run: {ts}  ",
        f"> Hardware: {gpu.get('name','unknown')} {gpu.get('vram_total','?')} · Driver {gpu.get('driver','?')}  ",
        f"> Model: `{llm_r['model']}` (Ollama, local)",
        "",
        "## LLM Latency",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Time-to-first-token p50 | **{llm_r['ttft_p50_ms']} ms** |",
        f"| Time-to-first-token p95 | {llm_r['ttft_p95_ms']} ms |",
        f"| Total response p50 | {llm_r['total_p50_ms']} ms |",
        f"| Total response p95 | {llm_r['total_p95_ms']} ms |",
        f"| Throughput (avg) | **{llm_r['tok_s_avg']} tok/s** |",
        f"| Throughput (peak) | {llm_r['tok_s_peak']} tok/s |",
        "",
        "### Per-prompt",
        "",
        "| Prompt | TTFT | Total | tok/s |",
        "|--------|------|-------|-------|",
    ]
    for p in llm_r.get("probes", []):
        if "error" in p:
            lines.append(f"| {p['label']} | — | — | ERROR |")
        else:
            lines.append(f"| {p['label']} | {p['ttft_ms']} ms | {p['total_ms']} ms | {p['tok_s']} |")

    lines += [
        "",
        "## Memory Retrieval",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Facts in DB | {mem_r['total_facts_in_db']} |",
        f"| Hit rate | {mem_r['hit_rate']*100:.0f}% |",
        f"| Category precision | {mem_r['category_precision']*100:.0f}% |",
        f"| Retrieval p50 | {mem_r['p50_ms']} ms |",
        f"| Retrieval p95 | {mem_r['p95_ms']} ms |",
    ]
    if mem_r.get("note"):
        lines.append(f"\n> Note: {mem_r['note']}")

    lines += [
        "",
        "## Tool Execution",
        "",
        "| Tool | Latency | Status |",
        "|------|---------|--------|",
    ]
    for r in tool_r.get("results", []):
        status = "✓" if r.get("ok") else "✗"
        lines.append(f"| {r['tool']} | {r['latency_ms']} ms | {status} |")

    lines += [
        "",
        f"**Tool success rate:** {tool_r['success_rate']*100:.0f}%",
        "",
        "---",
        "",
        "## System",
        "",
        f"| | |",
        f"|---|---|",
        f"| GPU | {gpu.get('name','—')} |",
        f"| VRAM total | {gpu.get('vram_total','—')} |",
        f"| VRAM used (at run) | {gpu.get('vram_used','—')} |",
        f"| GPU temp | {gpu.get('temp_c','—')} °C |",
        f"| SM clock | {gpu.get('sm_clock','—')} |",
        f"| Driver | {gpu.get('driver','—')} |",
        f"| Model | `{llm_r['model']}` |",
        f"| Quant | Q4\\_K\\_M (4-bit) |",
        f"| Runtime | Ollama (local) |",
    ]
    return "\n".join(lines) + "\n"

# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    from datetime import datetime, timezone

    init_db()
    db  = SessionLocal()
    llm = LLMClient()
    gpu = _gpu_info()
    ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sep = "-" * 56

    print(sep)
    print("  Luna Benchmark  —  RTX 3060 / Ollama")
    print(sep)
    print(f"  GPU    : {gpu.get('name','?')}  {gpu.get('vram_total','?')}")
    print(f"  VRAM   : {gpu.get('vram_used','?')} in use  @  {gpu.get('temp_c','?')}°C")
    print(f"  Model  : {settings.ollama_model}")
    print(sep)

    # LLM
    print("\n[1/3] LLM latency")
    t0 = time.perf_counter()
    llm_r = await bench_llm(llm)
    llm_d  = round(time.perf_counter() - t0, 1)
    _save(db, "llm", llm_r, [], llm_d)

    # Memory
    print("\n[2/3] Memory retrieval")
    t0 = time.perf_counter()
    mem_r = await bench_memory(db)
    mem_d  = round(time.perf_counter() - t0, 1)
    _save(db, "memory", mem_r, [], mem_d)

    # Tools
    print("\n[3/3] Tool execution")
    t0 = time.perf_counter()
    tool_r = await bench_tools()
    tool_d  = round(time.perf_counter() - t0, 1)
    _save(db, "tools", tool_r, [], tool_d)

    # Summary
    print(f"\n{sep}")
    print("  RESULTS SUMMARY")
    print(sep)
    print(f"  LLM TTFT p50     : {llm_r['ttft_p50_ms']} ms")
    print(f"  LLM total p50    : {llm_r['total_p50_ms']} ms")
    print(f"  LLM throughput   : {llm_r['tok_s_avg']} tok/s avg  /  {llm_r['tok_s_peak']} tok/s peak")
    print(f"  Memory hit rate  : {mem_r['hit_rate']*100:.0f}%  ({mem_r['total_facts_in_db']} facts in DB)")
    print(f"  Memory p50       : {mem_r['p50_ms']} ms")
    print(f"  Tool success     : {tool_r['success_rate']*100:.0f}%")
    print(sep)

    # Write markdown
    md = _markdown(gpu, ts, llm_r, mem_r, tool_r)
    out = ROOT / "docs" / "BENCHMARKS.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"\n  Saved -> {out}")
    print(f"  DB    -> {settings.db_path}")

    db.close()

if __name__ == "__main__":
    asyncio.run(main())
