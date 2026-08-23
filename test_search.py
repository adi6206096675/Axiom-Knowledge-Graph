import sys
import os

# Ensure clean path resolution
current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "app"))

try:
    from app.engine.indexer import AxiomIndexer  # type: ignore
except ImportError:
    from engine.indexer import AxiomIndexer  # type: ignore

def test_search(query_text: str):
    print(f"🔍 [AXIOM SEARCH TEST] Querying Qdrant for: '{query_text}'...")
    
    # Initialize the Axiom indexer
    indexer = AxiomIndexer(qdrant_url="http://localhost:6333", collection_name="axiom_facts")
    
    # Vectorize the query using your local NLP model
    query_vector = indexer.nlp.vectorize_text(query_text)
    
    # Search against the database
    results = indexer.search_facts(query_vector=query_vector, limit=3)
    
    if not results:
        print("⚠️ No matching records found above the similarity threshold.")
        return

    print(f"\n✨ Successfully retrieved {len(results)} matching records:\n" + "="*60)
    for i, hit in enumerate(results, 1):
        payload = hit.payload or {}
        print(f"[{i}] Point ID: {hit.id} | Match Score: {hit.score:.4f}")
        print(f"🔗 Source URL : {payload.get('source_url', 'N/A')}")
        print(f"📄 Real Text  :\n{payload.get('text', payload.get('document', '[MISSING TEXT PAYLOAD]'))}")
        print("="*60)

if __name__ == "__main__":
    # Allow passing custom search query via command line, default to "One Nation"
    query = sys.argv[1] if len(sys.argv) > 1 else "One Nation"
    test_search(query)