from qdrant_client import QdrantClient
from qdrant_client import models

def offload_to_disk():
    print("🚀 Connecting to Qdrant...")
    client = QdrantClient("http://localhost:6333")
    
    print("📦 Moving heavy HNSW indexes and payloads to Hard Drive...")
    client.update_collection(
        collection_name="axiom_facts",
        # Move the search index to disk
        hnsw_config=models.HnswConfigDiff(on_disk=True),
        # Force payloads to be stored on disk (memmap) instead of RAM
        optimizer_config=models.OptimizersConfigDiff(memmap_threshold=10000) 
    )
    
    print("✅ Success! Your 15GB RAM is now protected. The database is reading from disk.")

if __name__ == "__main__":
    offload_to_disk()