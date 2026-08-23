import sys
from qdrant_client import QdrantClient

def check_hydrated_records(limit: int):
    client = QdrantClient(url="http://localhost:6333", timeout=10)
    collection_name = "axiom_facts"
    
    print(f"🔍 Fetching the top {limit} records from Qdrant...\n" + "="*60)
    
    try:
        records, _ = client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        
        if not records:
            print("⚠️ No records found in the database.")
            return

        for i, record in enumerate(records, 1):
            payload = record.payload or {}
            source_url = payload.get('source_url', 'N/A')
            text_content = payload.get('text', '')
            
            # Format text preview cleanly
            if text_content:
                text_preview = text_content[:350] + "..." if len(text_content) > 350 else text_content
            else:
                text_preview = "[MISSING TEXT PAYLOAD]"
                
            print(f"[{i}] Point ID: {record.id}")
            print(f"🔗 URL: {source_url}")
            print(f"📄 Text Preview:\n{text_preview}\n" + "="*60)
            
    except Exception as e:
        print(f"❌ [DATABASE ERROR]: {e}")

if __name__ == "__main__":
    # Default to 5 records, but allow dynamic terminal arguments
    try:
        num_records = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    except ValueError:
        print("⚠️ Invalid number provided. Defaulting to 5.")
        num_records = 5
        
    check_hydrated_records(num_records)