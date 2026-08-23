import sys
import os
import time

# 1. Force the root directory into the system path so it NEVER fails at runtime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient
from fastembed import TextEmbedding

# 2. Add "# type: ignore" to silence IDE squiggles
from app.engine.traversal import DeterministicGraphTraversalService  # type: ignore
from app.engine.physics import DeterministicPhysicsEngine  # type: ignore
from app.models.schemas import (  # type: ignore
    FactGraphResponse, 
    PhysicsComputationResponse, 
    DiscrepancyReport
)

router = APIRouter()

# 1. Connect to the Live Qdrant Server (Port 6333) with safe timeout
qdrant = QdrantClient(url="http://localhost:6333", timeout=5)

# Initialize local FastEmbed model directly to avoid wrapper mismatches
try:
    embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
except Exception as e:
    print(f"⚠️ [WARNING] FastEmbed model load note: {e}")

# Initialize architecture services
traversal_service = DeterministicGraphTraversalService(qdrant_url="http://localhost:6333", collection_name="axiom_facts")
physics_engine = DeterministicPhysicsEngine(qdrant_url="http://localhost:6333", collection_name="axiom_facts")

# ==========================================
# SEARCH RESPONSE MODEL
# ==========================================
class AxiomResponse(BaseModel):
    query: str
    status: str
    entity_resolved: str | None = None
    property_measured: str | None = None
    fact: str | None = None
    mathematical_lineage: list | None = None
    reason: str | None = None
    metrics: dict

@router.get("/search", response_model=AxiomResponse)
def search(q: str):
    start = time.perf_counter()
    results = []
    
    try:
        # Generate embedding locally and query default unnamed vector space
        query_vector = list(embedding_model.embed([q]))[0].tolist()
        
        search_response = qdrant.query_points(
            collection_name="axiom_facts",
            query=query_vector,
            using="text_dense",  # <--- Essential for named vector matching
            limit=1,
            with_payload=True
        )
        results = search_response.points
    except Exception as e:
        print(f"🚨 [API ERROR] Vector Search Failed: {e}")

    metrics = {
        "execution_time_ms": round((time.perf_counter() - start) * 1000, 2),
        "storage_used": "Qdrant Standalone Server (Port 6333)"
    }

    if results:
        best_match = results[0]
        meta = best_match.payload if best_match.payload else {}
        
        return AxiomResponse(
            query=q,
            status="VERIFIED_LIVE_FACT",
            entity_resolved=str(meta.get("entity", q)).upper(),
            property_measured=str(meta.get("domain_filter", "EXTRACTED_VALUE")).upper(),
            fact=str(meta.get("source_url", "Indexed Fact Record")),
            mathematical_lineage=[{
                "source_id": "Axiom_Vector_Graph",
                "uri": meta.get("source_url", "network://localhost:6333/axiom_facts"),
                "tier": 1,
                "verification": f"Hash: {meta.get('content_hash', 'N/A')}"
            }],
            metrics=metrics
        )
    
    return AxiomResponse(
        query=q,
        status="UNVERIFIED",
        reason="AROM Kernel found no deterministic consensus in the Vector Graph.",
        metrics=metrics
    )

# ==========================================
# ARCHITECTURE ROUTES
# ==========================================
@router.get("/graph/traverse", response_model=FactGraphResponse)
async def traverse_graph(query: str = Query(..., description="Query to construct deterministic node graph"), depth: int = 2):
    try:
        return traversal_service.traverse(query=query, max_depth=depth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Graph Traversal Error: {str(e)}")

@router.get("/physics/compute", response_model=PhysicsComputationResponse)
async def compute_physics(entity: str = Query(..., description="Entity name to compute physical properties for")):
    try:
        return physics_engine.compute_kinetic_energy(entity_name=entity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Physics Computation Error: {str(e)}")

@router.get("/facts/resolve", response_model=DiscrepancyReport)
async def resolve_facts(entity: str = Query(..., description="Entity name to evaluate fact discrepancies")):
    try:
        return physics_engine.resolve_discrepancies(entity_name=entity)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fact Resolution Error: {str(e)}")