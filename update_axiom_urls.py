import re
import time
import logging
from collections import defaultdict
from typing import Dict, List
from qdrant_client import QdrantClient
from qdrant_client.http import models

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ---------------------------------------------------------------------------
# COMPREHENSIVE DOMAIN MAPPING DICTIONARY
# ---------------------------------------------------------------------------
DOMAIN_PATTERNS: Dict[str, List[str]] = {
    # --- Phase-1 Core Seeds ---
    "arxiv.org": ["arxiv", "preprint", "quantum", "relativity", "particle", "astrophysics"],
    "www.ieee.org": ["ieee", "circuit", "signal processing", "semiconductor", "electrical"],
    "www.acm.org": ["acm", "computing machinery", "siggraph", "algorithmic logic"],
    "www.nature.com": ["nature", "genome", "cellular", "molecular", "dna", "crispr"],
    "www.sciencedirect.com": ["sciencedirect", "elsevier", "chemical engineering", "biochemistry"],
    "cern.ch": ["cern", "hadron", "collider", "higgs", "neutrino"],
    "www.springer.com": ["springer", "academic publishing", "monograph"],
    "pubmed.ncbi.nlm.nih.gov": ["pubmed", "ncbi", "clinical trial", "pharmacology", "pathology"],
    
    # --- Indian Government & Official Data ---
    "www.rbi.org.in": ["rbi", "reserve bank", "monetary policy", "repo rate", "demonetisation", "rupee"],
    "india.gov.in": ["india.gov", "national portal of india", "government of india"],
    "data.gov.in": ["data.gov.in", "open government data india"],
    "meity.gov.in": ["meity", "electronics and information technology", "digital india"],
    "mohfw.gov.in": ["mohfw", "health and family welfare india", "icmr"],
    "uidai.gov.in": ["uidai", "aadhaar registration", "unique identification"],
    
    # --- Indian Education & Research ---
    "www.iitb.ac.in": ["iitb", "iit bombay", "indian institute of technology bombay"],
    "www.iitd.ac.in": ["iitd", "iit delhi", "indian institute of technology delhi"],
    "nptel.ac.in": ["nptel", "swayam", "e-learning india"],
    "www.ugc.ac.in": ["ugc", "university grants commission"],
    "www.csir.res.in": ["csir", "council of scientific and industrial research"],

    # --- Global Tech, Code & Discussions ---
    "stackoverflow.com": ["stackoverflow", "traceback", "exception", "nullpointer", "syntaxerror", "python", "rust"],
    "www.reddit.com": ["reddit", "subreddit", "r/"],
    "quora.com": ["quora", "question answered"],
    "medium.com": ["medium.com", "blog post"],
    "wikihow.com": ["wikihow", "how to"],
    "britannica.com": ["britannica", "encyclopedia"],

    # --- Tech News & Consumer ---
    "techradar.com": ["techradar", "gadget review"],
    "cnet.com": ["cnet", "tech news"],
    "tomsguide.com": ["tomsguide", "benchmark"],
    
    # --- Global News & Media ---
    "www.reuters.com": ["reuters", "wire service", "global news"],
    "www.bbc.com": ["bbc news", "bbc world"],
    "www.nytimes.com": ["nytimes", "new york times"],
    "www.theguardian.com": ["theguardian", "guardian news"],
    "www.forbes.com": ["forbes", "billionaire", "net worth"],
    
    # --- Indian News & Media ---
    "www.thehindu.com": ["the hindu", "thehindu news"],
    "indianexpress.com": ["indian express"],
    "hindustantimes.com": ["hindustan times"],
    "timesofindia.indiatimes.com": ["times of india", "toi"],
    "www.business-standard.com": ["business standard"],
    "www.livemint.com": ["livemint", "mint news"],
    "www.ndtv.com": ["ndtv news"]
}


def resolve_source_url_scale(entity: str, document: str) -> str:
    """Dynamically matches record text/entity against known domain patterns."""
    doc_lower = document.lower()
    entity_lower = entity.lower()
    
    # Iterate through domain matchers
    for domain, keywords in DOMAIN_PATTERNS.items():
        if any(kw in doc_lower or kw in entity_lower for kw in keywords):
            return f"https://{domain}"
            
    # Pop culture fallback
    if "pokemon" in entity_lower or "pokmon" in doc_lower:
        return "https://bulbapedia.bulbagarden.net"
        
    # Default fallback to clean Wikipedia reference
    clean_slug = re.sub(r'[^a-zA-Z0-9\s]', '', entity).strip().replace(' ', '_')
    if not clean_slug:
        clean_slug = "Main_Page"
    return f"https://en.wikipedia.org/wiki/{clean_slug}"


def run_qdrant_payload_migration(
    host: str = "127.0.0.1",
    port: int = 6333,
    collection_name: str = "axiom_facts",
    batch_size: int = 500
):
    """Scrolls through Qdrant and updates payloads in grouped network batches."""
    logging.info(f"Connecting to Qdrant at {host}:{port}...")
    client = QdrantClient(host=host, port=port)
    
    # Verify collection
    collections = [c.name for c in client.get_collections().collections]
    if collection_name not in collections:
        logging.error(f"Collection '{collection_name}' not found in Qdrant! Available: {collections}")
        return

    logging.info(f"Starting URL injection migration for collection: '{collection_name}'...")
    
    offset = None
    processed_total = 0
    updated_total = 0
    start_time = time.time()

    while True:
        # Scroll batch from Qdrant
        records, next_offset = client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False
        )
        
        if not records:
            break
            
        processed_total += len(records)
        
        # Group point IDs by their calculated URL to minimize Qdrant HTTP calls
        url_to_point_ids = defaultdict(list)
        
        for record in records:
            payload = record.payload or {}
            
            # Skip if valid source_url already exists
            if payload.get("source_url"):
                continue
                
            entity = payload.get("entity", "")
            document = payload.get("document", "")
            
            # Resolve target domain URL
            target_url = resolve_source_url_scale(entity, document)
            url_to_point_ids[target_url].append(record.id)

        # Batch execute set_payload calls
        batch_updated_count = 0
        for target_url, point_ids in url_to_point_ids.items():
            client.set_payload(
                collection_name=collection_name,
                payload={"source_url": target_url},
                points=point_ids
            )
            batch_updated_count += len(point_ids)
            
        updated_total += batch_updated_count
        
        # Progress metrics
        elapsed = time.time() - start_time
        rate = processed_total / elapsed if elapsed > 0 else 0
        logging.info(f"Scanned: {processed_total:,} | Injected URLs: {updated_total:,} | Speed: {rate:.1f} rec/sec")

        if next_offset is None:
            break
        offset = next_offset

    logging.info("=" * 60)
    logging.info(f"MIGRATION COMPLETE!")
    logging.info(f"Total Scanned: {processed_total:,}")
    logging.info(f"Total Injected: {updated_total:,}")
    logging.info(f"Total Time: {elapsed:.2f} seconds")
    logging.info("=" * 60)


if __name__ == "__main__":
    run_qdrant_payload_migration()