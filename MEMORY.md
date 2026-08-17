# Memory Architecture & Integration Guide

## 1. Memory Tool Choice: ChromaDB Vector Store

For the persistent memory layer, we chose an embedded vector store architecture using **ChromaDB** (backed by an automated in-memory vector fallback).

### Rationale
* **Semantic Similarity Retrieval:** Unlike key-value lookups, a vector store enables semantic retrieval where a newly perceived paragraph matches against past reflections on similar sentence patterns, nominalizations, or domain jargon.
* **Persistent Local State:** ChromaDB runs in embedded mode (`chromadb.PersistentClient`) without needing external cloud credentials or background server processes.
* **Episodic Learning:** It stores granular reflection traces (`semantic_drift`, `friction_failure`, `success_pattern`) along with temporal and score metadata.

---

## 2. Structure & Storage Format

The memory module (`agent/memory_manager.py`) exposes three core functions:

* `save(memory_text: str, metadata: dict) -> str`: Adds the critique or reflection string to the vector index with metadata (timestamp, critique type, score).
* `recall(query: str, limit: int = 3) -> list[str]`: Embeds the query text and retrieves the top-$K$ most semantically relevant reflections.
* `clear() -> None`: Purges the collection for benchmark tests and clean session resets.

### Stored Document Schema
Each memory entry contains:
```json
{
  "id": "mem_1723891234000",
  "document": "CRITICAL DRIFT: Rewrite dropped essential concepts (Retention: 40%). Must retain original technical nouns and metrics.",
  "metadata": {
    "type": "semantic_drift",
    "score": 4.5,
    "timestamp": 1723891234.0
  }
}