from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum

# ==========================================
# YOUR EXISTING SCHEMAS (UNCHANGED)
# ==========================================
class ProofNode(BaseModel):
    source_id: str
    uri: str
    tier: int
    verification: str

class Metrics(BaseModel):
    execution_time_ms: float
    storage_used: str

class AxiomResponse(BaseModel):
    query: str
    status: str
    entity_resolved: Optional[str] = None
    property_measured: Optional[str] = None
    fact: Optional[str] = None
    mathematical_lineage: Optional[List[ProofNode]] = None
    reason: Optional[str] = None
    metrics: Metrics


# ==========================================
# NEW ARCHITECTURE SCHEMAS (APPENDED)
# ==========================================
class FactType(str, Enum):
    PHYSICS = "physics"
    SEMANTIC = "semantic"
    ADVANCED_SEMANTIC = "advanced_semantic"

class GraphNode(BaseModel):
    id: str
    entity: str
    value: str
    fact_type: FactType
    source_document: str
    image_url: Optional[str] = None

class GraphEdge(BaseModel):
    source_entity: str
    target_entity: str
    relation: str
    evidence_document: str

class FactGraphResponse(BaseModel):
    query: str
    total_nodes: int
    total_edges: int
    nodes: List[GraphNode]
    edges: List[GraphEdge]

class ComputationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    INCOMPLETE_DATA = "INCOMPLETE_DATA"
    FAILED = "FAILED"

class PhysicsComputationResponse(BaseModel):
    entity: str
    status: ComputationStatus
    formula: Optional[str] = None
    input_mass: Optional[str] = None
    input_speed: Optional[str] = None
    computed_energy: Optional[str] = None
    numerical_joules: Optional[float] = None
    sources: List[str] = Field(default_factory=list)
    message: Optional[str] = None

class PropertyDiscrepancy(BaseModel):
    property_name: str
    total_facts: int
    unique_values: List[str]
    has_discrepancy: bool
    consensus_score: float

class DiscrepancyReport(BaseModel):
    entity: str
    total_facts_evaluated: int
    property_resolutions: List[PropertyDiscrepancy]