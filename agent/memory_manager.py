import os
import time
from typing import List, Dict, Any, Optional

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

class MemoryManager:
    """
    Episodic and semantic memory manager for the agentic loop.
    Persists critique traces, failure modes, and successful rewrite strategies.
    """
    def __init__(self, collection_name: str = "clarity_agent_memory", persist_dir: str = "./.agent_memory"):
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        
        if HAS_CHROMADB:
            os.makedirs(persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_dir)
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"description": "Episodic reflections and structural clarity critiques"}
            )
        else:
            self._fallback_store: List[Dict[str, Any]] = []

    def save(self, memory_text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Persists a reflection observation, critique, or rule.
        """
        doc_id = f"mem_{int(time.time() * 1000)}"
        meta = metadata or {}
        meta["timestamp"] = time.time()
        
        if HAS_CHROMADB:
            self.collection.add(
                documents=[memory_text],
                metadatas=[meta],
                ids=[doc_id]
            )
        else:
            self._fallback_store.append({
                "id": doc_id,
                "text": memory_text,
                "metadata": meta
            })
        return doc_id

    def recall(self, query: str, limit: int = 3) -> List[str]:
        """
        Semantically queries persistent memory for relevant past critiques and lessons.
        """
        if HAS_CHROMADB:
            count = self.collection.count()
            if count == 0:
                return []
            
            n_results = min(limit, count)
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            documents = results.get("documents", [[]])[0]
            return documents
        else:
            query_words = set(query.lower().split())
            ranked = sorted(
                self._fallback_store,
                key=lambda m: len(query_words & set(m["text"].lower().split())),
                reverse=True
            )
            return [item["text"] for item in ranked[:limit]]

    def clear(self) -> None:
        """
        Clears all stored memories.
        """
        if HAS_CHROMADB:
            self.client.delete_collection(self.collection_name)
            self.collection = self.client.get_or_create_collection(name=self.collection_name)
        else:
            self._fallback_store.clear()

# Global default instance
default_memory = MemoryManager()

def save(memory_text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    return default_memory.save(memory_text, metadata)

def recall(query: str, limit: int = 3) -> List[str]:
    return default_memory.recall(query, limit)

def clear() -> None:
    return default_memory.clear()