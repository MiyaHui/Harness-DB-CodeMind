from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np

from codemind.core.config import get_config
from codemind.core.models import Node

logger = logging.getLogger(__name__)


class EmbeddingIndex:
    def __init__(self) -> None:
        self._config = get_config()
        self._model: Any = None
        self._index: Any = None
        self._node_ids: list[str] = []
        self._embeddings: np.ndarray | None = None
        self._index_path = self._config.data_dir / "embedding_index"
        self._available = True

    def _get_model(self) -> Any:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self._config.embedding_model)
            except Exception as e:
                logger.warning(f"Embedding model not available: {e}")
                self._available = False
                raise RuntimeError(f"Embedding model not available: {e}")
        return self._model

    def build_index(self, nodes: list[Node]) -> int:
        if not nodes:
            return 0

        try:
            model = self._get_model()
        except RuntimeError:
            return 0

        try:
            texts = []
            self._node_ids = []

            for node in nodes:
                text = self._node_to_text(node)
                texts.append(text)
                self._node_ids.append(node.id)

            embeddings = model.encode(texts, show_progress_bar=False)
            self._embeddings = np.array(embeddings, dtype=np.float32)

            try:
                import faiss
                dimension = self._embeddings.shape[1]
                self._index = faiss.IndexFlatIP(dimension)
                faiss.normalize_L2(self._embeddings)
                self._index.add(self._embeddings)
            except ImportError:
                self._index = None

            self._save_index()
            return len(nodes)
        except Exception as e:
            logger.warning(f"Failed to build embedding index: {e}")
            return 0

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        if not self._available or self._embeddings is None or not self._node_ids:
            return []

        try:
            model = self._get_model()
        except RuntimeError:
            return []

        try:
            query_embedding = model.encode([query], show_progress_bar=False)
            query_embedding = np.array(query_embedding, dtype=np.float32)

            if self._index is not None:
                try:
                    import faiss
                    faiss.normalize_L2(query_embedding)
                    scores, indices = self._index.search(query_embedding, min(top_k, len(self._node_ids)))
                    results = []
                    for score, idx in zip(scores[0], indices[0]):
                        if idx >= 0 and idx < len(self._node_ids):
                            results.append((self._node_ids[idx], float(score)))
                    return results
                except Exception:
                    pass

            from numpy.linalg import norm
            query_norm = query_embedding / norm(query_embedding)
            emb_norm = self._embeddings / norm(self._embeddings, axis=1, keepdims=True)
            similarities = np.dot(emb_norm, query_norm.T).flatten()
            top_indices = np.argsort(similarities)[::-1][:top_k]

            return [(self._node_ids[i], float(similarities[i])) for i in top_indices]
        except Exception as e:
            logger.warning(f"Embedding search failed: {e}")
            return []

    def _node_to_text(self, node: Node) -> str:
        parts = [f"{node.type.value}: {node.name}"]
        if node.qualified_name:
            parts.append(f"qualified: {node.qualified_name}")
        if node.file_path:
            parts.append(f"file: {node.file_path}")
        if node.source_code:
            parts.append(f"code: {node.source_code[:500]}")
        for key, value in node.metadata.items():
            if isinstance(value, (str, int, float)):
                parts.append(f"{key}: {value}")
        return " | ".join(parts)

    def _save_index(self) -> None:
        if self._embeddings is None:
            return

        try:
            self._index_path.mkdir(parents=True, exist_ok=True)
            np.save(str(self._index_path / "embeddings.npy"), self._embeddings)
            with open(self._index_path / "node_ids.json", "w") as f:
                json.dump(self._node_ids, f)
        except Exception as e:
            logger.warning(f"Failed to save embedding index: {e}")

    def load_index(self) -> bool:
        emb_path = self._index_path / "embeddings.npy"
        ids_path = self._index_path / "node_ids.json"

        if not emb_path.exists() or not ids_path.exists():
            return False

        try:
            self._embeddings = np.load(str(emb_path))
            with open(ids_path) as f:
                self._node_ids = json.load(f)

            try:
                import faiss
                dimension = self._embeddings.shape[1]
                self._index = faiss.IndexFlatIP(dimension)
                faiss.normalize_L2(self._embeddings)
                self._index.add(self._embeddings)
            except ImportError:
                self._index = None

            return True
        except Exception:
            return False
