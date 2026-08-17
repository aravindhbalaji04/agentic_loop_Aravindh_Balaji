import os
import yaml
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "agent": {
        "max_iterations": 6,
        "target_friction_score": 0.0,
        "semantic_threshold": 0.55,
        "token_budget_warning": 4000
    },
    "llm": {
        "model_name": "gemini-2.5-flash",
        "temperature": 0.3,
        "timeout_seconds": 30.0
    },
    "retry": {
        "max_retries": 3,
        "initial_delay_seconds": 1.0,
        "backoff_multiplier": 2.0,
        "jitter": True
    },
    "memory": {
        "backend": "chromadb",
        "persist_dir": "./.agent_memory",
        "collection_name": "clarity_agent_memory",
        "recall_limit": 3
    },
    "logging": {
        "log_file": "agent_execution.jsonl",
        "log_to_stdout": True
    }
}

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            user_cfg = yaml.safe_load(f) or {}
            # Deep merge dicts
            for k, v in user_cfg.items():
                if isinstance(v, dict) and k in config:
                    config[k].update(v)
                else:
                    config[k] = v
                    
    # Environment variable overrides
    if os.getenv("GEMINI_MODEL"):
        config["llm"]["model_name"] = os.getenv("GEMINI_MODEL")
    if os.getenv("MAX_ITERATIONS"):
        config["agent"]["max_iterations"] = int(os.getenv("MAX_ITERATIONS"))
    if os.getenv("TOKEN_BUDGET"):
        config["agent"]["token_budget_warning"] = int(os.getenv("TOKEN_BUDGET"))
        
    return config