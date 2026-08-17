import re
from typing import Dict, Any, Callable

# 1. JSON Schema Tool Definitions
tools_schema = {
    "score_clarity_friction": {
        "description": "Calculates structural friction metrics: counts vague pronoun openers, smothered nominalizations, and transition markers. Lower friction indicates clearer text.",
        "parameters": {
            "text": {
                "type": "string",
                "description": "The rewritten paragraph candidate to evaluate."
            }
        },
        "required": ["text"]
    },
    "check_semantic_integrity": {
        "description": "Measures token overlap ratio between the candidate and original text to prevent factual loss, hallucination, or excessive deletion.",
        "parameters": {
            "original_text": {
                "type": "string",
                "description": "The immutable source ground truth."
            },
            "candidate_text": {
                "type": "string",
                "description": "The newly generated paragraph to verify."
            },
            "threshold": {
                "type": "number",
                "description": "Minimum token overlap ratio (default: 0.55)."
            }
        },
        "required": ["original_text", "candidate_text"]
    }
}

# 2. Tool Handlers
def handle_score_clarity_friction(text: str) -> Dict[str, Any]:
    """Calculates cognitive friction penalties and flow bonuses."""
    words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
    
    # Ambiguous starters (e.g., "This is...", "It was...")
    vague_openers = len(re.findall(
        r'(?:^|[.!?]\s+)(this|it|these|those)\s+(is|was|are|were|has|shows|means)', 
        text, 
        re.I
    ))
    
    # Nominalizations (smothered verbs ending in -tion, -ment, -ance, etc.)
    nominalizations = len([w for w in words if re.search(r'(tion|ment|ance|ence|ibility)$', w) and len(w) > 6])
    
    # Explicit logical transition markers
    transitions = len(re.findall(
        r'\b(however|therefore|because|for example|in contrast|as a result|consequently|specifically|furthermore)\b', 
        text, 
        re.I
    ))
    
    # Friction Score formula: (Lower = Clearer)
    friction_score = round((vague_openers * 2.0) + (nominalizations * 1.0) - (transitions * 1.0), 2)
    
    return {
        "friction_score": friction_score,
        "vague_openers_count": vague_openers,
        "nominalizations_count": nominalizations,
        "transitions_count": transitions,
        "is_clear": friction_score <= 0.0
    }

def handle_check_semantic_integrity(original_text: str, candidate_text: str, threshold: float = 0.55) -> Dict[str, Any]:
    """Guards against meaning drift and entity loss."""
    orig_tokens = set(re.findall(r'\b[a-zA-Z0-9]{4,}\b', original_text.lower()))
    cand_tokens = set(re.findall(r'\b[a-zA-Z0-9]{4,}\b', candidate_text.lower()))
    
    if not orig_tokens:
        return {"retention_ratio": 1.0, "safe": True}
        
    overlap = len(orig_tokens & cand_tokens)
    ratio = round(overlap / len(orig_tokens), 2)
    
    return {
        "retention_ratio": ratio,
        "safe": ratio >= threshold
    }

# Tool Registry mapping names to callable handlers
TOOL_HANDLERS: Dict[str, Callable] = {
    "score_clarity_friction": handle_score_clarity_friction,
    "check_semantic_integrity": handle_check_semantic_integrity
}