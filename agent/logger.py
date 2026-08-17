import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

class StructuredStepLogger:
    def __init__(self, log_file: str = "agent_execution.jsonl", log_to_stdout: bool = True):
        self.log_file = log_file
        self.log_to_stdout = log_to_stdout

    def log_step(
        self,
        iteration: int,
        step_name: str,
        input_summary: Any,
        output_summary: Any,
        latency_ms: float,
        tokens_used: int = 0,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "iteration": iteration,
            "step_name": step_name,
            "input_summary": str(input_summary)[:180],
            "output_summary": str(output_summary)[:220],
            "latency_ms": round(latency_ms, 2),
            "tokens_used": tokens_used,
            "error": error
        }

        # Write to JSONL file
        if self.log_file:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

        # Optional console echo
        if self.log_to_stdout:
            status_tag = f"[ERROR: {error}]" if error else "[OK]"
            print(f"[LOG {entry['timestamp'][11:19]}] Iter {iteration} | {step_name.upper():<7} | {latency_ms:.1f}ms | {status_tag}")

        return entry