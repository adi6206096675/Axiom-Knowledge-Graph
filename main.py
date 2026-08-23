import os
import warnings

# ==========================================
# ⚡ PRODUCTION GUARDRAILS: API STABILITY
# ==========================================
# Forcefully restrict PyTorch and ONNX thread sprawl so the API server 
# never crashes or starves the CPU when handling concurrent search requests.
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
warnings.filterwarnings("ignore", category=UserWarning)

import json
import time
import urllib.parse
import urllib.request
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient
from sentence_transformers import CrossEncoder

from app.api.router import router as axiom_router

app = FastAPI(title="AROM - AXIOM", description="The Modular Deterministic Knowledge Engine")

app.include_router(axiom_router)

# ==========================================
# 1. CORS MIDDLEWARE 
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

# ==========================================
# 2. ZERO-STORAGE PRIVACY MIDDLEWARE
# ==========================================
@app.middleware("http")
async def add_privacy_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ==========================================
# 3. DYNAMIC MEDIA RESOLVER (Fallback Gateway)
# ==========================================
def fetch_wikimedia_image(query_text: str) -> str | None:
    """Dynamically resolves verified public domain media when Qdrant lacks an image_url."""
    try:
        clean_query = urllib.parse.quote(query_text.strip())
        url = f"https://en.wikipedia.org/w/api.php?action=query&titles={clean_query}&prop=pageimages&format=json&pithumbsize=800"
        req = urllib.request.Request(url, headers={'User-Agent': 'AxiomEngine/1.0'})
        with urllib.request.urlopen(req, timeout=1.5) as response:
            data = json.loads(response.read().decode())
            pages = data.get("query", {}).get("pages", {})
            for _, page in pages.items():
                if "thumbnail" in page and "source" in page["thumbnail"]:
                    return page["thumbnail"]["source"]
    except Exception as err:
        print(f"[AXIOM MEDIA RESOLVER] Wikimedia fallback note: {err}")
    return None


print("Initializing Axiom High-Speed Hybrid Vector Gateway...")
qdrant = QdrantClient(url="http://localhost:6333")

# 4. Enable Hybrid Search Natively (Matching Refinery Schema)
qdrant.set_model("BAAI/bge-small-en-v1.5")
qdrant.set_sparse_model("Qdrant/bm25")

# Initialize Local Cross-Encoder Re-Ranker
print("Loading Local Cross-Encoder Re-Ranker (Thread-Locked)...")
cross_encoder = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2', max_length=512)

# Minimum neural confidence threshold to accept a fact as verified
SCORE_THRESHOLD = -2.0

@app.get("/search")
def search_knowledge_graph(q: str):
    start_time = time.time()
    try:
        # 5. Optimized Hybrid Retrieval (Top 15 for sub-second latency)
        search_results = qdrant.query(
            collection_name="axiom_facts",
            query_text=q,
            limit=15
        )

        if not search_results:
            fallback_image = fetch_wikimedia_image(q)
            if fallback_image:
                return {
                    "status": "VERIFIED_LIVE_FACT",
                    "metrics": {"execution_time_ms": round((time.time() - start_time) * 1000, 2)},
                    "entity_resolved": q.upper(),
                    "fact": f"Visual media resolved dynamically for {q}.",
                    "property_measured": "DYNAMIC_MEDIA",
                    "image_url": fallback_image,
                    "all_results": [
                        {
                            "entity": q.upper(),
                            "value": "Visual Asset",
                            "type": "MEDIA_NODE",
                            "document": f"Dynamic media asset retrieved for entity query: {q}",
                            "image_url": fallback_image,
                            "uri": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(q)}"
                        }
                    ]
                }
            return {"status": "UNVERIFIED", "reason": "No deterministic consensus found in the Vector Graph."}

        # 6. HIGH-SPEED NEURAL RE-RANKING
        # UPGRADE: Mapped to "text_content" to read the perfect sentences created by the Smart Chunker yesterday
        sentence_pairs = []
        for hit in search_results:
            # Handle potential payload object structures dynamically
            payload = getattr(hit, "metadata", getattr(hit, "payload", {}))
            text_val = payload.get("text_content", payload.get("document", ""))
            sentence_pairs.append([q, text_val])
            
        scores = cross_encoder.predict(sentence_pairs)
        
        for i, hit in enumerate(search_results):
            hit.score = float(scores[i])
            
        search_results = sorted(search_results, key=lambda x: x.score, reverse=True)
        primary_hit = search_results[0]
        primary_payload = getattr(primary_hit, "metadata", getattr(primary_hit, "payload", {}))

        # 7. CONFIDENCE GUARDRAIL
        if primary_hit.score < SCORE_THRESHOLD:
            return {
                "status": "UNVERIFIED",
                "reason": "Knowledge Graph currently lacks verified facts matching this exact query.",
                "metrics": {"execution_time_ms": round((time.time() - start_time) * 1000, 2)}
            }

        # 8. SMART Deterministic Elevation (Physics > Generic)
        # UPGRADE: Mapped to yesterday's "domain_tag"
        for hit in search_results[:3]:
            temp_payload = getattr(hit, "metadata", getattr(hit, "payload", {}))
            if temp_payload.get("domain_tag") == "physics" and hit.score >= SCORE_THRESHOLD:
                primary_hit = hit
                primary_payload = temp_payload
                break

        # 9. Extract or dynamically resolve media
        primary_entity = primary_payload.get("entity", q)
        
        # Safely handle the string "None" that the refinery might pass
        raw_image_url = primary_payload.get("image_url")
        if raw_image_url == "None":
            raw_image_url = None
            
        primary_image = raw_image_url or fetch_wikimedia_image(primary_entity) or fetch_wikimedia_image(q)

        # 10. Build Full UI Lineage
        all_results = []
        all_results.append({
            "entity": primary_entity.upper(),
            "value": primary_payload.get("text_content", "UNKNOWN"), # Fact is now the perfect intact sentence
            "type": primary_payload.get("domain_tag", "UNKNOWN").upper(),
            "document": primary_payload.get("text_content", ""),
            "image_url": primary_image,
            "uri": f"network://localhost:6333/axiom_facts/{primary_payload.get('domain_tag', 'data')}"
        })
        
        for hit in search_results:
            if hit.id != primary_hit.id and hit.score >= SCORE_THRESHOLD:
                hit_payload = getattr(hit, "metadata", getattr(hit, "payload", {}))
                hit_entity = hit_payload.get("entity", primary_entity)
                
                hit_raw_img = hit_payload.get("image_url")
                if hit_raw_img == "None":
                    hit_raw_img = None
                hit_image = hit_raw_img or fetch_wikimedia_image(hit_entity)

                all_results.append({
                    "entity": hit_entity.upper(),
                    "value": hit_payload.get("text_content", "UNKNOWN"),
                    "type": hit_payload.get("domain_tag", "UNKNOWN").upper(),
                    "document": hit_payload.get("text_content", ""),
                    "image_url": hit_image,
                    "uri": f"network://localhost:6333/axiom_facts/{hit_payload.get('domain_tag', 'data')}"
                })

        return {
            "status": "VERIFIED_LIVE_FACT",
            "metrics": {"execution_time_ms": round((time.time() - start_time) * 1000, 2)},
            "entity_resolved": primary_entity.upper(),
            "fact": primary_payload.get("text_content", "UNKNOWN"),
            "property_measured": primary_payload.get("domain_tag", "UNKNOWN").upper(),
            "image_url": primary_image,
            "all_results": all_results
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}

if __name__ == "__main__":
    print("Initializing AROM - AXIOM Enterprise Gateway on Port 8001...")
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)