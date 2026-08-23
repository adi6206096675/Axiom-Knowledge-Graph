import time
import hashlib
from typing import Optional, List, Any

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# Robust import resolution with type-ignore to clear unknown symbol errors
try:
    from .nlp import HybridNLPRefinery  # type: ignore
except ImportError:
    try:
        from engine.nlp import HybridNLPRefinery  # type: ignore
    except ImportError:
        from app.engine.nlp import HybridNLPRefinery  # type: ignore


class AxiomIndexer:
    def __init__(self, qdrant_url: str = "http://localhost:6333", collection_name: str = "axiom_facts") -> None:
        self.client = QdrantClient(url=qdrant_url)
        self.collection_name = collection_name
        self.nlp = HybridNLPRefinery()

    def _compute_hash(self, content: str) -> str:
        """Deduplication & Canonicalization: Generates a unique SHA-256 signature."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def create_point(
        self, 
        text_content: str, 
        source_url: str, 
        image_url: Optional[str] = None,
        domain_tag: str = "science"
    ) -> Optional[PointStruct]:
        if not text_content:
            return None

        # 1. Deduplication fingerprinting
        content_hash = self._compute_hash(text_content)

        # 2. Generate Hybrid Vectors
        text_vector = self.nlp.vectorize_text(text_content)
        clip_vector = self.nlp.vectorize_multimodal(text_content, image_bytes=None)

        # 3. Explainability & Lineage Metadata Payload
        payload = {
            "text": text_content,          # Stores raw text for UI frontend display
            "document": text_content,      # Added for engine compatibility
            "source_url": source_url,
            "image_url": image_url,
            "timestamp": time.time(),
            "content_hash": content_hash,
            "domain_filter": domain_tag,
            "embedding_types": ["fastembed_text", "clip_multimodal"],
            "confidence_score": 0.95,
            "lineage": {
                "spider": "rust_crawler_v2",
                "refiner": "engine_indexer"
            }
        }

        # Generate a deterministic 64-bit integer ID from the SHA-256 hash
        point_id = int(hashlib.md5(content_hash.encode()).hexdigest()[:15], 16)

        return PointStruct(
            id=point_id,
            vector={
                "text_dense": text_vector,
                "clip_multimodal": clip_vector
            },
            payload=payload
        )

    def upsert_batch(self, points: List[PointStruct]) -> None:
        """Pushes a batch of verified points into the SQ8 compressed index."""
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def search_facts(self, query_vector: List[float], limit: int = 1) -> Any:
        """Executes a semantic search against the hybrid index using modern Qdrant API."""
        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                using="text_dense",
                limit=limit,
                score_threshold=0.50,
                with_payload=True  # <--- Added this to pull the rich text data!
            )
            return response.points
        except Exception as e:
            print(f"⚠️ [SEARCH ERROR] Query execution failed: {e}")
            return []