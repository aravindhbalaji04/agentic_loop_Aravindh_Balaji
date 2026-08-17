# Agent Scaffolding & Reliability Architecture

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

---

## 5. Sample Terminal Execution Outputs

Below are the terminal execution logs captured during program runs under different configuration parameters in `config.yaml`.

### Run 1: Execution with `max_iterations: 6` in `config.yaml`

```shell
$ python3 main.py
======================================================================
STARTING HARNESS-WRAPPED PRODUCTION AGENTIC LOOP
======================================================================
ORIGINAL PARAGRAPH:
"The execution of the database migration was carried out by the infrastructure engineers. This is because of the fact that latency minimization was needed for client satisfaction. It resulted in throughput optimization, although resource utilization increased."

[LOG 06:12:52] Iter 0 | PERCEIVE | 0.4ms | [OK]

[PERCEIVE] Baseline Friction Score: 7.0

========================= ITERATION 1 =========================
Direct use of automatic function calling (AFC) in Models.generate_content is not recommended. Instead, we recommend to use AFC in Chat.send_message. Similarly, direct use of AFC in Models.generate_content_stream is not recommended. Instead, we recommend to use AFC in Chat.send_message_stream.
[LOG 06:12:58] Iter 1 | REASON  | 5565.5ms | [OK]
[REASON Trace]: The original text contains passive phrasing, wordy transitions ('because of the fact that'), and ambiguous pronouns ('This', 'It'). To improve clarity, the revision activates passive verbs, explicitly names subjects like the database migration, and streamlines transitions while preserving all core metrics and concepts.
[LOG 06:12:58] Iter 1 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because minimizing latency was necessary to ensure client satisfaction. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:12:58] Iter 1 | REFLECT | 164.1ms | [OK]
[REFLECT Feedback]: SUCCESSFUL PATTERN: Friction reduced from 7.0 to 2.0. Refine further.

========================= ITERATION 2 =========================
[LOG 06:13:06] Iter 2 | REASON  | 7521.4ms | [OK]
[REASON Trace]: The current draft was evaluated to eliminate passive constructions and ambiguous pronouns while preserving core metrics and causal links. A slight refinement ensures maximum clarity and low structural friction without semantic loss.
[LOG 06:13:06] Iter 2 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because minimizing latency was necessary to ensure client satisfaction. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:13:06] Iter 2 | REFLECT | 167.4ms | [OK]
[REFLECT Feedback]: INEFFECTIVE PATTERN: Failed to reduce friction (2.0 vs best 2.0).

========================= ITERATION 3 =========================
[LOG 06:13:10] Iter 3 | REASON  | 4564.5ms | [OK]
[REASON Trace]: The revision eliminates passive voice and vague pronouns by establishing infrastructure engineers as the primary subject and directly linking latency reduction to client satisfaction. Explicit transitional phrasing connects the cause and effect regarding throughput and resource utilization.
[LOG 06:13:10] Iter 3 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because client satisfaction required minimizing latency. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:13:11] Iter 3 | REFLECT | 168.1ms | [OK]
[REFLECT Feedback]: INEFFECTIVE PATTERN: Failed to reduce friction (2.0 vs best 2.0).

========================= ITERATION 4 =========================
[LOG 06:13:17] Iter 4 | REASON  | 5815.3ms | [OK]
[REASON Trace]: The current draft was analyzed for structural friction and nominalization issues. To enhance clarity, passive constructions were further streamlined while maintaining explicit causal relationships and core terminology.
[LOG 06:13:17] Iter 4 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because client satisfaction required minimized latency. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:13:17] Iter 4 | REFLECT | 154.5ms | [OK]
[REFLECT Feedback]: INEFFECTIVE PATTERN: Failed to reduce friction (2.0 vs best 2.0).

========================= ITERATION 5 =========================
[LOG 06:13:23] Iter 5 | REASON  | 6143.8ms | [OK]
[REASON Trace]: The current version effectively eliminates vague pronouns and passive voice while preserving key metrics. The plan focuses on streamlining the causal clause to further reduce friction while ensuring full semantic integrity.
[LOG 06:13:23] Iter 5 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because minimizing latency was necessary for client satisfaction. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:13:23] Iter 5 | REFLECT | 159.8ms | [OK]
[REFLECT Feedback]: INEFFECTIVE PATTERN: Failed to reduce friction (2.0 vs best 2.0).

========================= ITERATION 6 =========================
[LOG 06:13:32] Iter 6 | REASON  | 8506.3ms | [OK]
[REASON Trace]: To improve structural clarity, active phrasing is used to attribute the database migration directly to the infrastructure engineers. Clear causal transitions explicitly connect the need for latency minimization to client satisfaction, showing how the migration optimized throughput while increasing resource utilization.
[LOG 06:13:32] Iter 6 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because minimizing latency was necessary to ensure client satisfaction. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:13:32] Iter 6 | REFLECT | 159.9ms | [OK]
[REFLECT Feedback]: INEFFECTIVE PATTERN: Failed to reduce friction (2.0 vs best 2.0).

======================================================================
RUN SUMMARY [STATUS: PARTIAL | ITERATIONS: 6]
======================================================================
FINAL OUTPUT:
"Infrastructure engineers executed the database migration because minimizing latency was necessary to ensure client satisfaction. Consequently, the migration optimized throughput, although resource utilization increased."
FINAL FRICTION SCORE: 2.0
```

### Run 2: Execution with `max_iterations: 3` in `config.yaml`

```shell
$ python3 main.py
======================================================================
STARTING HARNESS-WRAPPED PRODUCTION AGENTIC LOOP
======================================================================
ORIGINAL PARAGRAPH:
"The execution of the database migration was carried out by the infrastructure engineers. This is because of the fact that latency minimization was needed for client satisfaction. It resulted in throughput optimization, although resource utilization increased."

[LOG 06:13:55] Iter 0 | PERCEIVE | 0.4ms | [OK]

[PERCEIVE] Baseline Friction Score: 7.0

========================= ITERATION 1 =========================
Direct use of automatic function calling (AFC) in Models.generate_content is not recommended. Instead, we recommend to use AFC in Chat.send_message. Similarly, direct use of AFC in Models.generate_content_stream is not recommended. Instead, we recommend to use AFC in Chat.send_message_stream.
[LOG 06:14:01] Iter 1 | REASON  | 5988.0ms | [OK]
[REASON Trace]: The original text relies on passive phrasing, nominalizations, and ambiguous pronouns such as 'this' and 'it'. To resolve structural friction, the revision uses active voice with infrastructure engineers as the subject, replaces wordy transitions with concise causal connectives, and explicitly names the migration as the cause of throughput optimization and increased resource utilization.
[LOG 06:14:01] Iter 1 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because client satisfaction required minimizing latency. Consequently, the migration optimized throughput, although it increased resource utilization."
[LOG 06:14:01] Iter 1 | REFLECT | 151.3ms | [OK]
[REFLECT Feedback]: SUCCESSFUL PATTERN: Friction reduced from 7.0 to 2.0. Refine further.

========================= ITERATION 2 =========================
[HARNESS WARN] Attempt 1/3 failed: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}} -> Backing off for 1.34s...
[LOG 06:14:27] Iter 2 | REASON  | 26346.3ms | [OK]
[REASON Trace]: The current draft was evaluated to ensure complete clarity and eliminate remaining vague pronouns. By explicitly attributing actions and maintaining strong connective transitions, structural friction is minimized while fully preserving semantic integrity and key operational metrics.
[LOG 06:14:27] Iter 2 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because client satisfaction required minimizing latency. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:14:28] Iter 2 | REFLECT | 158.2ms | [OK]
[REFLECT Feedback]: INEFFECTIVE PATTERN: Failed to reduce friction (2.0 vs best 2.0).

========================= ITERATION 3 =========================
[LOG 06:14:36] Iter 3 | REASON  | 8427.5ms | [OK]
[REASON Trace]: The candidate paragraph was refined to eliminate the ambiguous pronoun 'it' in the concluding clause while preserving all key metrics, active constructions, and explicit logical transitions.
[LOG 06:14:36] Iter 3 | ACT     | 0.1ms | [OK]
[ACT Candidate]: "Infrastructure engineers executed the database migration because client satisfaction required minimizing latency. Consequently, the migration optimized throughput, although resource utilization increased."
[LOG 06:14:36] Iter 3 | REFLECT | 162.8ms | [OK]
[REFLECT Feedback]: Infinite loop detected: Model emitted identical output in consecutive iterations.

[LOOP HALTED] Infinite loop detected: Model emitted identical output in consecutive iterations.

======================================================================
RUN SUMMARY [STATUS: STUCK | ITERATIONS: 3]
======================================================================
FINAL OUTPUT:
"Infrastructure engineers executed the database migration because client satisfaction required minimizing latency. Consequently, the migration optimized throughput, although it increased resource utilization."
FINAL FRICTION SCORE: 2.0
```