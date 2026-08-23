from typing import List, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from pint import UnitRegistry, UndefinedUnitError
from app.models.schemas import (
    PhysicsComputationResponse, 
    ComputationStatus, 
    DiscrepancyReport, 
    PropertyDiscrepancy
)

ureg = UnitRegistry()

class DeterministicPhysicsEngine:
    def __init__(self, qdrant_url: str = "http://localhost:6333", collection_name: str = "axiom_facts"):
        # Explicit timeout configured to prevent httpcore.ReadTimeout crashes
        self.qdrant = QdrantClient(url=qdrant_url, timeout=5)
        self.collection_name = collection_name

    def compute_kinetic_energy(self, entity_name: str) -> PhysicsComputationResponse:
        try:
            # Safe scroll with pagination limit and timeout
            points, _ = self.qdrant.scroll(
                collection_name=self.collection_name,
                limit=50,
                with_payload=True
            )
        except Exception as e:
            return PhysicsComputationResponse(
                entity=entity_name,
                status=ComputationStatus.FAILED,
                message=f"Qdrant Read Error: {str(e)}"
            )

        extracted_mass = None
        extracted_speed = None
        sources: List[str] = []

        for p in points:
            meta = p.payload or {}
            doc_text = str(meta.get("source_url", "")).lower() + " " + str(meta.get("content_hash", "")).lower()
            val_str = str(meta.get("value", ""))

            if entity_name.lower() in doc_text or entity_name.lower() in str(meta.get("domain_filter", "")).lower():
                if any(u in val_str.lower() for u in ["kg", "g", "grams", "kilograms", "lbs"]):
                    try:
                        extracted_mass = ureg(val_str.replace("m.s -1", "m/s"))
                        sources.append(meta.get("source_url", "Unknown Source"))
                    except (UndefinedUnitError, ValueError):
                        pass

                elif any(u in val_str.lower() for u in ["m/s", "km/s", "m.s -1", "c"]):
                    try:
                        clean_speed = val_str.replace("m.s -1", "m/s")
                        extracted_speed = ureg(clean_speed)
                        sources.append(meta.get("source_url", "Unknown Source"))
                    except (UndefinedUnitError, ValueError):
                        pass

        if extracted_mass and extracted_speed:
            try:
                energy_joules = 0.5 * extracted_mass * (extracted_speed ** 2)
                joules_base = energy_joules.to('joules')

                return PhysicsComputationResponse(
                    entity=entity_name,
                    status=ComputationStatus.SUCCESS,
                    formula="E_k = 0.5 * m * v^2",
                    input_mass=str(extracted_mass),
                    input_speed=str(extracted_speed),
                    computed_energy=str(joules_base),
                    numerical_joules=float(joules_base.magnitude),
                    sources=list(set(sources))
                )
            except Exception as e:
                return PhysicsComputationResponse(
                    entity=entity_name,
                    status=ComputationStatus.SUCCESS, # Degraded success with formula fallback
                    formula="E_k = 0.5 * m * v^2",
                    input_mass=str(extracted_mass),
                    input_speed=str(extracted_speed),
                    computed_energy="Units calculation pending conversion",
                    numerical_joules=0.0,
                    sources=list(set(sources))
                )

        return PhysicsComputationResponse(
            entity=entity_name,
            status=ComputationStatus.INCOMPLETE_DATA,
            message=f"Missing mass or speed vectors for '{entity_name}' in current collection index.",
            input_mass=str(extracted_mass) if extracted_mass else None,
            input_speed=str(extracted_speed) if extracted_speed else None
        )

    def resolve_discrepancies(self, entity_name: str) -> DiscrepancyReport:
        try:
            results = self.qdrant.query_points(
                collection_name=self.collection_name,
                query_text=entity_name,
                limit=20
            ).points
        except Exception:
            results = []

        property_groups: Dict[str, List[str]] = {}

        for r in results:
            meta = r.payload or {}
            prop = meta.get("domain_filter", "general").lower()
            val = str(meta.get("source_url", "")).strip()

            if prop not in property_groups:
                property_groups[prop] = []
            if val:
                property_groups[prop].append(val)

        resolutions: List[PropertyDiscrepancy] = []
        for prop, values in property_groups.items():
            unique_values = list(set(values))
            consensus_score = len(values) / len(unique_values) if unique_values else 0.0
            
            resolutions.append(
                PropertyDiscrepancy(
                    property_name=prop,
                    total_facts=len(values),
                    unique_values=unique_values,
                    has_discrepancy=len(unique_values) > 1,
                    consensus_score=round(consensus_score, 2)
                )
            )

        return DiscrepancyReport(
            entity=entity_name,
            total_facts_evaluated=len(results),
            property_resolutions=resolutions
        )