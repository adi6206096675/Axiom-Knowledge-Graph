from typing import Set, List
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.models.schemas import FactGraphResponse, GraphNode, GraphEdge, FactType

class DeterministicGraphTraversalService:
    def __init__(self, qdrant_url: str = "http://localhost:6333", collection_name: str = "axiom_facts"):
        self.qdrant = QdrantClient(url=qdrant_url)
        self.collection_name = collection_name
        self.qdrant.set_model("BAAI/bge-small-en-v1.5")
        self.qdrant.set_sparse_model("Qdrant/bm25")

    def traverse(self, query: str, max_depth: int = 2, limit_per_hop: int = 10) -> FactGraphResponse:
        # Use high-level .query() matching main.py to natively support FastEmbed text queries
        try:
            seed_points = self.qdrant.query(
                collection_name=self.collection_name, 
                query_text=query, 
                limit=limit_per_hop
            )
        except Exception:
            try:
                seed_points = self.qdrant.query_points(
                    collection_name=self.collection_name, 
                    query=query,
                    limit=limit_per_hop
                ).points
            except Exception:
                seed_points = []

        visited_entities: Set[str] = set()
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []
        frontier: Set[str] = set()

        for point in seed_points:
            meta = getattr(point, 'metadata', None) or getattr(point, 'payload', None) or {}
            entity = str(meta.get("entity", "")).lower().strip()
            if entity and entity not in visited_entities:
                visited_entities.add(entity)
                frontier.add(entity)
                nodes.append(
                    GraphNode(
                        id=f"node_{len(nodes)}",
                        entity=entity,
                        value=str(meta.get("value", "")),
                        fact_type=meta.get("type", FactType.SEMANTIC),
                        source_document=str(meta.get("document", "")),
                        image_url=meta.get("image_url")
                    )
                )

        depth = 1
        while depth < max_depth and frontier:
            next_frontier: Set[str] = set()
            for current_entity in list(frontier)[:5]:
                try:
                    connected, _ = self.qdrant.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=models.Filter(
                            should=[
                                models.FieldCondition(key="entity", match=models.MatchText(text=current_entity)),
                                models.FieldCondition(key="value", match=models.MatchText(text=current_entity))
                            ]
                        ),
                        limit=5,
                        with_payload=True
                    )
                except Exception:
                    connected = []

                for item in connected:
                    meta = getattr(item, 'metadata', None) or getattr(item, 'payload', None) or {}
                    c_entity = str(meta.get("entity", "")).lower().strip()
                    if c_entity and c_entity not in visited_entities:
                        visited_entities.add(c_entity)
                        next_frontier.add(c_entity)

                        nodes.append(
                            GraphNode(
                                id=f"node_{len(nodes)}",
                                entity=c_entity,
                                value=str(meta.get("value", "")),
                                fact_type=meta.get("type", FactType.SEMANTIC),
                                source_document=str(meta.get("document", ""))
                            )
                        )

                        edges.append(
                            GraphEdge(
                                source_entity=current_entity,
                                target_entity=c_entity,
                                relation=str(meta.get("type", "linked_to")),
                                evidence_document=str(meta.get("document", ""))
                            )
                        )

            frontier = next_frontier
            depth += 1

        return FactGraphResponse(
            query=query,
            total_nodes=len(nodes),
            total_edges=len(edges),
            nodes=nodes,
            edges=edges
        )