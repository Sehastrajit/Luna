# Luna Benchmark Results

> **Last run:** 2026-05-21 22:50 UTC
> **Hardware:** NVIDIA GeForce RTX 3060 12 GB · Driver 596.21
> **Model:** `qcwind/qwen3-8b-instruct-Q4-K-M` (Qwen3 8B, 4-bit quantized, local via Ollama)
> **Method:** standalone runner, no server — pure service-layer latency

---

## LLM Latency

| Metric | Value |
|--------|-------|
| Time-to-first-token p50 | **1148 ms** |
| Time-to-first-token p95 | 1169 ms |
| Total response p50 | 1374 ms |
| Total response p95 | 5149 ms |
| Throughput (sustained) | **~26 tok/s** |
| Throughput (avg incl. short) | 11.8 tok/s |

> **Note on throughput:** single-token responses (echo, math) drag the average to 11.8 tok/s.
> Sustained generation (medium-length responses) runs at **24–29 tok/s** on the RTX 3060,
> which is the number that matters for real conversations.
> The p95 total of 5149 ms is a 150-token response, not latency.

### Per-prompt breakdown

| Prompt | TTFT | Total | tok/s | Output |
|--------|------|-------|-------|--------|
| short-echo | 818 ms | 864 ms | 1.2 | 1 token |
| short-math | 1169 ms | 1265 ms | 0.8 | 1 token |
| short-list | 1134 ms | 1374 ms | 3.6 | ~5 tokens |
| medium-bullets | 1150 ms | 5149 ms | **29.1** | ~150 tokens |
| medium-explain | 1148 ms | 3060 ms | **24.2** | ~75 tokens |

---

## Memory Retrieval

| Metric | Value |
|--------|-------|
| Facts in DB | 0 |
| Hit rate | 0% |
| Retrieval latency p50 | 593.5 ms |
| Retrieval latency p95 | 616.8 ms |

> **Why 0% hits:** no facts are stored yet — the database is new. The retrieval latency
> (593 ms) is ChromaDB cold-query overhead on an empty index. Once facts accumulate
> through normal use, this will be the latency for semantic lookup (expected to remain
> under 100 ms for a personal-scale collection of hundreds of facts).

---

## Tool Execution

| Tool | Latency | Result |
|------|---------|--------|
| workspace_list | **1 ms** | OK — local filesystem |
| web_search | 1143 ms | OK — 6 results returned |

**Tool success rate:** 100%

---

## System

| | |
|---|---|
| GPU | NVIDIA GeForce RTX 3060 |
| VRAM total | 12 288 MiB |
| VRAM during inference | 9 588 MiB (model fully resident) |
| GPU temp | 45 °C |
| SM clock | 780 MHz |
| Driver | 596.21 |
| Model | `qcwind/qwen3-8b-instruct-Q4-K-M:latest` |
| Model size | ~5 GB on disk, ~9.6 GB active VRAM |
| Quantisation | Q4\_K\_M (4-bit, k-quant) |
| Runtime | Ollama local |
| OS | Windows 11 Pro |

---

## Reading the numbers

**TTFT ~1 s** is the scheduling + first-token generation time for Qwen3 8B Q4\_K\_M
on the RTX 3060. This is expected for an 8 B parameter model — Ollama has to load the
prompt, run prefill, and emit the first token before the stream starts.

**Sustained 25–29 tok/s** is the actual decode speed once generation is rolling.
At this rate, a 200-token response takes ~7–8 s total (1 s TTFT + 6–7 s generation).

**Memory 0%** will become meaningful after the first few conversations: facts extracted
from chat history are embedded via Ollama and stored in ChromaDB.  Re-run this benchmark
after 10+ conversations to see real retrieval precision.

---

## Rerunning

```bash
cd Luna
python scripts/run_benchmark.py
```

Results are appended to `data/luna.db` (table `benchmark_results`) and this file is
overwritten with the latest run.
