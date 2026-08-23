import warnings
# Suppress cosmetic deprecation warnings to keep the terminal clean
warnings.filterwarnings("ignore", category=UserWarning)

import os
import sys
import redis
import spacy
import re
import time
import hashlib
import uuid
import json
import gc
import torch
from pint import UnitRegistry, UndefinedUnitError

# FIX: Bulletproof path injection.
current_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, "app"))

try:
    from engine.indexer import AxiomIndexer  # type: ignore
except ImportError:
    from app.engine.indexer import AxiomIndexer  # type: ignore

print("🔥 Initializing AROM Advanced Logic Refinery & Hybrid Vector Engine...")
nlp = spacy.load("en_core_web_sm")

# 1. Redis acts as high-speed buffer queue
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# 2. Initialize Qdrant via our custom AxiomIndexer to handle Hybrid Named Vectors
indexer = AxiomIndexer(qdrant_url="http://localhost:6333", collection_name="axiom_facts")

ureg = UnitRegistry(autoconvert_offset_to_baseunit=True)

# Enhanced mapping including Energy
DIMENSION_MAP = {
    "speed": "[length] / [time]",
    "mass": "[mass]",
    "temperature": "[temperature]",
    "distance": "[length]",
    "time": "[time]",
    "energy": "[mass] * [length] ** 2 / [time] ** 2"
}

def get_deterministic_id(text: str) -> str:
    hash_hex = hashlib.md5(text.encode('utf-8')).hexdigest()
    return str(uuid.UUID(hex=hash_hex))

def compute_content_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def normalize_text(text: str) -> str:
    text = re.sub(r'OBJ < > STREAM.*?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\.mw-parser-output\S+', '', text)
    text = re.sub(r'\{\\displaystyle.*?\}', '', text)
    text = re.sub(r'\{.*?\}', '', text)
    text = re.sub(r'\[\s*\d+\s*\]', '', text)
    text = text.replace('−', '-')
    text = re.sub(r'(?:×|x|\*)\s*10\s+(\-?\d+)\b', r'× 10^\1', text, flags=re.IGNORECASE)
    text = re.sub(r'(\d+(?:\.\d+)?)\s+10\s+(\-?\d+)\b', r'\1 × 10^\2', text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.replace('\xa0', ' ').replace('⋅', '.')
    return re.sub(r'\s+', ' ', text).strip()

def smart_chunk_text(text: str, max_size: int = 10000) -> list:
    """
    UPGRADE: Intelligently batches text at natural sentence boundaries.
    Prevents SpaCy RAM bloat without cutting a single character or bisecting sentences.
    """
    # Split text by common sentence terminators followed by spaces, keeping the data intact
    raw_sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sentence in raw_sentences:
        # If adding the next sentence exceeds our RAM safety limit, finalize the current chunk
        if len(current_chunk) + len(sentence) > max_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
        else:
            current_chunk += sentence + " "
            
    # Catch any remaining text
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
        
    return chunks

def verify_physical_dimension(value_str: str, property_type: str) -> bool:
    try:
        clean_val = re.sub(r'\s*×\s*10\^\-?\d+', '', value_str)
        clean_val = clean_val.replace("m.s -1", "m/s").replace("°C", "degC")
        quantity = ureg(clean_val)
        for key, expected_dimension in DIMENSION_MAP.items():
            if key in property_type:
                return str(quantity.dimensionality) == expected_dimension
        return False 
    except (UndefinedUnitError, ValueError, AttributeError):
        return False

def extract_semantic_relations(sent_str: str, sent_doc) -> list:
    extracted_facts = []
    relational_patterns = [
        r'(?P<value>[A-Z][a-zA-Z\s\.\-]+?)\s+(?:is|was).*?(?P<property>ceo|president|founder|capital|author|inventor).*?of\s+(?P<target>[A-Z][a-zA-Z\s\.\-]+)',
        r'(?:the\s+)?(?P<property>ceo|president|founder|capital|author|inventor).*?of\s+(?P<target>[A-Z][a-zA-Z\s\.\-]+).*?(?:is|was)\s+(?P<value>[A-Z][a-zA-Z\s\.\-]+)'
    ]
    for pattern in relational_patterns:
        match = re.search(pattern, sent_str, re.IGNORECASE)
        if match:
            val = match.group('value').strip(' .!,;')
            prop = match.group('property').lower().strip()
            target = match.group('target').strip(' .!,;')
            valid_entities = [ent.text.strip(' .!,;') for ent in sent_doc.ents if ent.label_ in ["PERSON", "ORG", "GPE", "LOC"]]
            if val in valid_entities or target in valid_entities:
                extracted_facts.append({"key": f"{prop} of {target.lower()}", "value": val})
    return extracted_facts

def advanced_transformer_extraction(sent_str: str, sent_doc) -> list:
    extracted = []
    for token in sent_doc:
        if token.pos_ in ["VERB", "AUX"] and token.dep_ == "ROOT":
            subjects = [w for w in token.lefts if w.dep_ in ["nsubj", "nsubjpass"]]
            objects = [w for w in token.rights if w.dep_ in ["attr", "dobj", "acomp", "pobj"]]
            if subjects and objects:
                subj_text = " ".join([w.text for w in subjects[0].subtree]).strip().lower()
                obj_text = " ".join([w.text for w in objects[0].subtree]).strip()
                if len(subj_text) > 2 and subj_text not in ["it", "this", "that", "they", "he", "she", "we"]:
                    extracted.append({"key": subj_text, "value": obj_text})
    return extracted

def process_text_block(text_block: str, source_url: str = "", image_url: str = "None") -> int:
    clean_text = normalize_text(text_block)
    facts_extracted = 0
    points_to_upsert = []
    doc = None  # FIX: Pre-initialize doc to prevent unbound variable error

    chunks = smart_chunk_text(clean_text, max_size=10000)

    for chunk in chunks:
        if len(chunk) < 50:
            continue
            
        # FIX: Sleep added during chunk processing to prevent connection timeouts
        time.sleep(0.05)
            
        try:
            doc = nlp(chunk)
            for sent in doc.sents:
                sent_str = sent.text.strip()
                if len(sent_str) < 15:
                    continue
                    
                sent_doc = nlp(sent_str)
                fact_found = False
                
                # 1. STRICT PHYSICS
                numeric_match = re.search(
                    r'\b\d+(?:[ \.,]\d+)*(?:\s*×\s*10\^\-?\d+)?\s*(?:m/s|km/s|c|kg|meters|seconds|°C|K|J|eV|m\.s\s*\-1)\b', 
                    sent_str, 
                    re.IGNORECASE
                )
                
                if numeric_match:
                    val = numeric_match.group(0)
                    for noun_chunk in sent_doc.noun_chunks:
                        entity_key = noun_chunk.text.replace("the ", "").strip().lower()
                        if len(entity_key) > 3 and any(dim in entity_key for dim in DIMENSION_MAP.keys()):
                            if verify_physical_dimension(val, entity_key):
                                point = indexer.create_point(
                                    text_content=sent_str, source_url=source_url,
                                    image_url=image_url if image_url != "None" else None, domain_tag="physics"
                                )
                                if point:
                                    points_to_upsert.append(point)
                                    facts_extracted += 1
                                    fact_found = True

                # 2. STRICT SEMANTIC
                if not fact_found:
                    for _ in extract_semantic_relations(sent_str, sent_doc):
                        point = indexer.create_point(
                            text_content=sent_str, source_url=source_url,
                            image_url=image_url if image_url != "None" else None, domain_tag="relational"
                        )
                        if point:
                            points_to_upsert.append(point)
                            facts_extracted += 1
                            fact_found = True

                # 3. ADVANCED DEPENDENCY
                if not fact_found:
                    for _ in advanced_transformer_extraction(sent_str, sent_doc):
                        point = indexer.create_point(
                            text_content=sent_str, source_url=source_url,
                            image_url=image_url if image_url != "None" else None, domain_tag="advanced_semantic"
                        )
                        if point:
                            points_to_upsert.append(point)
                            facts_extracted += 1
                            fact_found = True

                # 4. BASE KNOWLEDGE FALLBACK
                if not fact_found and len(sent_str.split()) > 8:
                    point = indexer.create_point(
                        text_content=sent_str, source_url=source_url,
                        image_url=image_url if image_url != "None" else None, domain_tag="general"
                    )
                    if point:
                        points_to_upsert.append(point)
                        facts_extracted += 1

                # Clean up local references instantly to prevent memory pooling
                del sent_doc
                
        except Exception as e:
            print(f"⚠️ [EXTRACTION CRASH ON CHUNK]: {e}")
            continue

    if points_to_upsert:
        try:
            indexer.upsert_batch(points_to_upsert)
        except Exception as e:
            print(f"❌ [QDRANT UPSERT FAILED]: {e}")

    # FIX: Safely delete variables only if assigned
    del chunks
    if doc is not None:
        del doc
    gc.collect()

    return facts_extracted

def start_refinery_loop():
    print("[REFINERY] Listening for multi-modal structured JSON stream from Rust Crawler...")
    blocks_processed = 0
    while True:
        try:
            item = r.blpop("arom_text_pipeline", timeout=2)
            if item:
                _, raw_data = item
                raw_text = raw_data.decode('utf-8') if isinstance(raw_data, bytes) else str(raw_data)
                
                try:
                    payload = json.loads(raw_text)
                    text_content = payload.get("text", "")
                    source_url = payload.get("source_url", "")
                    image_url = payload.get("image_url", "None")
                except json.JSONDecodeError:
                    text_content = raw_text
                    source_url = ""
                    image_url = "None"
                
                blocks_processed += 1
                if blocks_processed % 50 == 0:
                    print(f"🔄 [REFINERY] Ingested and NLP scanned {blocks_processed} HTML blocks...")
                    
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    
                process_text_block(text_content, source_url, image_url)

                time.sleep(0.01)
                
        except KeyboardInterrupt:
            print("\n🛑 Gracefully shutting down refinery loop...")
            break
        except Exception as e:
            print(f"⚠️ [REFINERY LOOP ERROR]: {e}")
            time.sleep(1)

if __name__ == "__main__":
    start_refinery_loop()