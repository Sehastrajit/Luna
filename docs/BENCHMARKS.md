# Luna Benchmark Results

> **Run:** 2026-05-21 23:01 UTC  
> **Hardware:** NVIDIA GeForce RTX 3060  12288 MB VRAM  (driver 596.21)  
> **CPU:** Intel64 Family 6 Model 151 Stepping 2, GenuineIntel  31.8 GB RAM  
> **OS:** Windows 11  
> **Model:** `qcwind/qwen3-8b-instruct-Q4-K-M:latest`  provider: `ollama`  
> **Runs per probe:** 3  (cold call reported separately; warm stats exclude it)

## Summary

| Metric | Value | Notes |
|--------|-------|-------|
| LLM TTFT (warm, p50) | **763 ms** | first token latency |
| LLM TTFT (warm, p95) | 799.6 ms | tail latency |
| Sustained throughput | **35 tok/s** | long-form prompts only |
| Memory retrieval p50 | 599 ms | ChromaDB vector search |
| Tool success rate    | 100% | safe tools only |

## LLM Latency

> Throughput (tok/s) is only reported for long-form prompts (50+ output tokens).
> Short prompts measure TTFT responsiveness, not decode speed.

### Distribution (warm calls, all probes)

| Metric | Value |
|--------|-------|
| TTFT mean | 763 ms  (p50 763  p95 800  sd 26) |
| Total mean | 2232 ms  (p50 1038  p95 5783  sd 1795) |
| Throughput | 35 tok/s  (p50 35  p95 48  sd 9) |

### Per-prompt

| Probe | Cold TTFT | Warm TTFT (mean) | Warm Total (mean) | tok/s |
|-------|-----------|------------------|-------------------|-------|
| echo | 3881 ms | 748 ms | 766 ms | N/A (short) |
| arithmetic | 4106 ms | 778 ms | 842 ms | N/A (short) |
| short-list | 3796 ms | 761 ms | 1038 ms | N/A (short) |
| medium | 3829 ms | 794 ms | 5168 ms | 36 tok/s |
| long | 3775 ms | 736 ms | 3346 ms | 34 tok/s |

## Memory Retrieval

| Metric | Value |
|--------|-------|
| Facts in DB | 0 |
| Hit rate | N/A (< 10 facts) |
| Retrieval latency | 599 ms  (p50 601  p95 619  sd 10) |

> Re-run after 10+ conversations for quality metrics.

## Tool Execution

**Overall success rate:** 100%

| Tool | Success Rate | Latency (mean) | p95 |
|------|-------------|----------------|-----|
| workspace_list | 100% | 1 ms | 1 ms |
| web_search | 100% | 1030 ms | 1318 ms |

## System

| | |
|---|---|
| Accelerator | NVIDIA GeForce RTX 3060 |
| VRAM total | 12288 MB |
| VRAM used (at run) | 3530 MB |
| Temperature | 50 C |
| Driver | 596.21 |
| CPU | Intel64 Family 6 Model 151 Stepping 2, GenuineIntel |
| RAM | 31.8 GB |
| OS | Windows 11 |
| Model | `qcwind/qwen3-8b-instruct-Q4-K-M:latest` |
| Provider | ollama |

---

## Provider Comparison

> Both runs executed 2026-05-21 on the same machine (RTX 3060, Win11).  
> Groq is a cloud inference API; Ollama runs the model locally on the GPU.

| Metric | Ollama — Qwen3 8B Q4_K_M (local) | Groq — llama-3.3-70b-versatile (cloud) |
|--------|----------------------------------|----------------------------------------|
| TTFT warm p50 | 763 ms | **482 ms** |
| TTFT warm p95 | 800 ms | 611 ms |
| Throughput p50 | 35 tok/s | **210 tok/s** |
| Cold TTFT | ~3.8 s (model load) | ~500 ms (no cold penalty) |
| Memory retrieval | 599 ms (local ChromaDB) | N/A |
| Tool success rate | **100%** | N/A (LLM suite only) |
| Cost | $0 (local GPU) | Pay-per-token |
| Privacy | Local — no data leaves machine | Cloud API |

**When to use each:**
- **Ollama (local)**: Privacy-sensitive tasks, offline use, zero API cost, tool execution
- **Groq (cloud)**: Fastest responses, long context, 70B quality, no GPU required

---

## Rerunning

```bash
# Local Ollama (default)
python scripts/run_benchmark.py

# Groq cloud
python scripts/run_benchmark.py --provider groq --suite llm --runs 3

# Full suite with more runs
python scripts/run_benchmark.py --suite all --runs 5
```
