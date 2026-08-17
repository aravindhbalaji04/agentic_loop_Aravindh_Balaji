# Agentic Patterns Research & Architecture Choice

This document provides a comparative analysis of five foundational LLM agent patterns and details the architecture chosen for the iterative paragraph refinement loop.

---

## 1. Research on Agentic Patterns

### Chain-of-Thought (CoT)
Chain-of-Thought (CoT) decomposes complex multi-step reasoning into intermediate textual steps before outputting a final answer. By explicitly generating a sequential train of thought in a single inference call, CoT mitigates reasoning jumps and improves accuracy on mathematical and symbolic tasks. However, it remains a single-pass, feedforward approach without runtime tool execution, external environmental feedback, or error recovery mechanisms.

### ReAct (Reason + Act)
ReAct interleaves reasoning traces with task-specific actions (such as API calls or database lookups) and environmental observations. In each cycle, the model produces a thought explaining what it needs, executes a tool call, and incorporates the resulting observation back into its context window. While powerful for dynamic exploration and data retrieval, basic ReAct lacks an episodic memory buffer for multi-trial self-evaluation across distinct revisions of an entire artifact.

### Reflexion
Reflexion extends standard agent loops by introducing verbal reinforcement and episodic memory. When an agent attempts a task, an external evaluator or diagnostic suite scores the output and provides feedback. The agent reflects on this feedback, logs a critique of its mistake into a persistent memory buffer, and attempts the task again. This pattern enables self-correction and rollback capabilities without requiring model fine-tuning or parameter updates.

### Tree of Thoughts (ToT)
Tree of Thoughts (ToT) generalizes beyond linear reasoning by framing problem-solving as search over an explicit tree of thoughts. At each step, the agent generates multiple candidate thoughts, evaluates their individual promise via heuristic or model-based scoring, and explores paths using search algorithms like Breadth-First Search (BFS) or Depth-First Search (DFS). While robust for combinatorial problems (e.g., Game of 24 or crossword puzzles), it incurs heavy computational and token costs.

### Language Agent Tree Search (LATS)
LATS unifies Language Models with Monte Carlo Tree Search (MCTS), incorporating external tool calling, value evaluations, and state backpropagation. Nodes represent intermediate states and actions, which are simulated, scored, and updated through selection, expansion, simulation, and backpropagation steps. LATS represents the state of the art for complex decision tasks with large state spaces (such as game playing or multi-file coding), but introduces significant algorithmic overhead.

---

## 2. Chosen Pattern: Reflexion (with Checkpoint & Rollback)

### Applied Architecture
The paragraph rewriting engine implements the **Reflexion** pattern, structured into a 4-phase cognitive lifecycle: `perceive -> reason -> act -> reflect`.

### Why This Fits the Use Case
1. **Episodic Memory for Multi-Trial Convergence:** Rather than blindly re-prompting, each rejection reason (e.g., semantic drift or unaddressed nominalizations) is recorded in working memory to steer subsequent iterations away from previous mistakes.
2. **Deterministic Checkpoints & Safe Rollback:** If a candidate rewrite erases facts (failing semantic integrity), the `reflect` step discards the candidate entirely, prevents state corruption, and reverts working memory to the prior best checkpoint.
3. **Objective Diagnostic Feedback:** Reflexion leverages deterministic external tools (`score_clarity_friction` and `check_semantic_integrity`) to ground its self-evaluation in verifiable structural metrics rather than subjective model preferences.