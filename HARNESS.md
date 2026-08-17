# Agent Scaffolding & Reliability Architecture (Milestone 3)

## 1. Overview
This document outlines the production scaffolding implemented around the core `perceive -> reason -> act -> reflect` loop to defend against runtime failures, rate limits, non-deterministic model outputs, and runaway resource consumption.

---

## 2. Failure Modes & Defenses

| Failure Mode | Root Cause | Harness Defense & Fallback Strategy |
| :--- | :--- | :--- |
| **API Rate Limits / Timeouts** | LLM provider throttling (HTTP 429 / 504). | **Exponential Backoff with Full Jitter:** Retries up to `max_retries` with randomized exponential delay to prevent herd throttling. |
| **Malformed JSON Output** | LLM drops schema or includes raw conversational markdown. | **Multi-Tier Parser Fallback:** Regex extraction of `"candidate_text"` and raw string recovery if `json.loads` fails. |
| **Tool Crashes / Exceptions** | Unexpected characters or regex engine errors. | **Guarded Tool Wrapper (`safe_tool_call`):** Traps exceptions, logs warnings, and returns safe observation dicts so the loop does not crash. |
| **Memory Backend Outage** | Vector store / disk read errors. | **Graceful Memory Fallback (`safe_memory_read`):** Proceeds without prior memory context and logs a warning. |
| **Infinite Ping-Pong Loops** | Model produces identical output or repeats identical critique. | **Loop Guardrail (`check_guardrails`):** Detects consecutive identical states and halts with a `STUCK` status. |
| **Max Iterations Exhausted** | Target score not met within iteration limit. | **Partial Checkpoint Delivery:** Returns the best accepted version with a `PARTIAL` status flag. |
| **Token Budget Overrun** | Long text accumulation in context. | **Cumulative Token Tracking:** Tracks token usage across cycles and raises warning logs if budget is exceeded. |

---

## 3. Observability & Structured Step Logging

Every step across every iteration records a structured JSON record in `agent_execution.jsonl` with:
* `timestamp`: ISO-8601 UTC timestamp.
* `iteration`: Current iteration index.
* `step_name`: `perceive`, `reason`, `act`, or `reflect`.
* `input_summary`: Truncated preview of incoming context.
* `output_summary`: Summary of produced candidate/metrics.
* `latency_ms`: Step execution duration in milliseconds.
* `error`: Exception details (if any).

---

## 4. Configuration Management

All hyperparameters, retry coefficients, memory settings, and limits are externalized in `config.yaml` and can be overridden with environment variables (`GEMINI_MODEL`, `MAX_ITERATIONS`, `TOKEN_BUDGET`), eliminating hardcoded values from the codebase.