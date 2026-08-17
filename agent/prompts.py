SYSTEM_PROMPT = """You are an expert structural editor focusing on clarity over brevity.
Your objective:
1. Disentangle dense, nested phrasing.
2. Resolve ambiguous pronouns ('it', 'this', 'they') by naming the explicit subject.
3. Use connective transitions ('because', 'therefore', 'for example') to clarify causal and logical relationships.
4. Preserve all essential nouns, metrics, and core meaning from the original source text."""

REASONING_PROMPT_TEMPLATE = """Ground Truth Original Text:
\"{original_text}\"

Current Best Working Version:
\"{best_text}\"

Episodic Memory & Prior Trial Feedback:
{memory_context}

Available Tools:
{tools_doc}

Task:
Analyze the structural friction in the current draft and formulate a concrete plan.
Respond in strict JSON with the following keys:
{{
  "reasoning_trace": "Detailed diagnostic and explanation of the revision plan.",
  "chosen_action": "rewrite_and_evaluate",
  "candidate_text": "The full revised paragraph text."
}}"""