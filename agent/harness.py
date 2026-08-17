import time
import random
import json
import re
from typing import Callable, Any, Dict, List, Tuple

class AgentHarness:
    def __init__(self, config: Dict[str, Any], logger: Any):
        self.config = config
        self.logger = logger
        self.total_tokens_used = 0
        self.consecutive_stuck_tracker: List[str] = []

    def execute_with_retry(
        self,
        fn: Callable[[], str],
        iteration: int,
        step_name: str,
        fallback_prompt_fn: Callable[[], str] = None
    ) -> Tuple[str, float]:
        """
        Executes an LLM or network function with exponential backoff and jitter.
        Recovers from rate limits, timeouts, and network drops.
        """
        retry_cfg = self.config["retry"]
        max_retries = retry_cfg.get("max_retries", 3)
        delay = retry_cfg.get("initial_delay_seconds", 1.0)
        multiplier = retry_cfg.get("backoff_multiplier", 2.0)
        use_jitter = retry_cfg.get("jitter", True)

        start_time = time.time()
        last_exception = None

        for attempt in range(1, max_retries + 1):
            try:
                # If we failed previously and have a fallback prompt builder, try simplified route
                response_text = fn()
                latency_ms = (time.time() - start_time) * 1000
                return response_text, latency_ms
            except Exception as e:
                last_exception = e
                err_msg = f"Attempt {attempt}/{max_retries} failed: {str(e)}"
                
                if attempt == max_retries:
                    break

                sleep_time = delay * (multiplier ** (attempt - 1))
                if use_jitter:
                    sleep_time = random.uniform(0.5 * sleep_time, 1.5 * sleep_time)

                print(f"[HARNESS WARN] {err_msg} -> Backing off for {sleep_time:.2f}s...")
                time.sleep(sleep_time)

        # Fallback Strategy: If exhausted, run fallback prompt if available
        if fallback_prompt_fn:
            print("[HARNESS FALLBACK] Standard calls failed. Attempting simplified prompt fallback...")
            try:
                fallback_res = fallback_prompt_fn()
                latency_ms = (time.time() - start_time) * 1000
                return fallback_res, latency_ms
            except Exception as fe:
                last_exception = fe

        latency_ms = (time.time() - start_time) * 1000
        self.logger.log_step(
            iteration=iteration,
            step_name=step_name,
            input_summary="LLM Inference Call",
            output_summary="Failed after max retries",
            latency_ms=latency_ms,
            error=str(last_exception)
        )
        raise RuntimeError(f"Harness failed after {max_retries} attempts: {last_exception}")

    def safe_parse_plan_json(self, raw_response: str) -> Dict[str, Any]:
        """
        Robust parser with fallback strategies for malformed JSON, markdown fences,
        or unescaped string candidates.
        """
        clean = raw_response.strip()
        
        # 1. Strip markdown fences if present
        if "```json" in clean:
            clean = clean.split("```json")[1].split("```")[0].strip()
        elif "```" in clean:
            clean = clean.split("```")[1].split("```")[0].strip()

        # 2. Standard JSON load
        try:
            return json.loads(clean)
        except Exception:
            pass

        # 3. Fallback: Regex extraction of keys
        try:
            candidate_match = re.search(r'"candidate_text"\s*:\s*"(.*?)"(?:\s*,\s*"|\s*})', clean, re.DOTALL)
            trace_match = re.search(r'"reasoning_trace"\s*:\s*"(.*?)"(?:\s*,\s*"|\s*})', clean, re.DOTALL)
            
            candidate = candidate_match.group(1).replace('\\"', '"') if candidate_match else clean
            trace = trace_match.group(1).replace('\\"', '"') if trace_match else "Regex fallback extracted candidate."

            return {
                "reasoning_trace": trace,
                "chosen_action": "rewrite_and_evaluate",
                "candidate_text": candidate
            }
        except Exception:
            # 4. Ultimate Fallback: Treat the whole string as candidate
            return {
                "reasoning_trace": "Malformed JSON recovery: raw string used as candidate.",
                "chosen_action": "rewrite_and_evaluate",
                "candidate_text": raw_response.strip().strip('"')
            }

    def safe_tool_call(self, tool_fn: Callable, **kwargs) -> Dict[str, Any]:
        """
        Executes a diagnostic tool inside a safety boundary.
        Returns a graceful observation dictionary on failure.
        """
        try:
            return tool_fn(**kwargs)
        except Exception as e:
            print(f"[HARNESS WARN] Tool execution failed: {str(e)}. Returning graceful observation.")
            return {
                "error": str(e),
                "safe": True, # Allow loop to continue without crashing
                "retention_ratio": 0.55,
                "friction_score": 99.0,
                "is_clear": False,
                "is_fallback": True
            }

    def safe_memory_read(self, memory_recall_fn: Callable[[str, int], List[str]], query: str, limit: int) -> List[str]:
        """
        Memory read failure fallback: Continue gracefully without memory if vector store is down.
        """
        try:
            return memory_recall_fn(query, limit)
        except Exception as e:
            print(f"[HARNESS WARN] Memory read failed: {str(e)}. Proceeding without memory.")
            return []

    def check_guardrails(self, reflection_instruction: str, candidate_text: str) -> Dict[str, Any]:
        """
        Detects infinite loops and track budget warnings.
        """
        # 1. Infinite loop check: identical reflection or text twice in a row
        self.consecutive_stuck_tracker.append(f"{reflection_instruction.strip()}::{candidate_text.strip()}")
        if len(self.consecutive_stuck_tracker) >= 2:
            if self.consecutive_stuck_tracker[-1] == self.consecutive_stuck_tracker[-2]:
                return {
                    "is_stuck": True,
                    "status": "STUCK",
                    "reason": "Infinite loop detected: Model emitted identical output in consecutive iterations."
                }

        # 2. Token budget tracking
        token_limit = self.config["agent"].get("token_budget_warning", 4000)
        # Approximate 1 token ~= 4 characters
        self.total_tokens_used += len(candidate_text) // 4 + 250
        
        if self.total_tokens_used > token_limit:
            print(f"[GUARDRAIL WARN] Cumulative token usage ({self.total_tokens_used}) exceeded budget ({token_limit}).")

        return {"is_stuck": False, "status": "OK"}