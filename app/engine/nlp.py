import os
import io
import re
import torch
import clip
import spacy
from PIL import Image
from fastembed import TextEmbedding
from typing import Dict, Any, Optional

print("🔥 Initializing AXIOM Symbolic Parser (SpaCy)...")
# Loading the base model. This acts as the engine for your Knowledge Graph Overlay.
nlp = spacy.load("en_core_web_sm")

class HybridNLPRefinery:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"🧠 Initializing FastEmbed & CLIP on: {self.device.upper()}")
        
        # 1. FastEmbed for text
        # 1. FastEmbed for text (Forced single-thread to prevent CPU hijacking)
        self.text_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5", threads=1)
        
        # 2. CLIP for Multimodal
        self.clip_model, self.clip_preprocess = clip.load("ViT-B/32", device=self.device)

    def vectorize_text(self, text: str) -> list:
        """Generates dense embeddings for semantic search."""
        embeddings = list(self.text_model.embed([text]))
        return embeddings[0].tolist()

    # FIX 1 & 2: Added Optional[bytes] to explicitly allow None values under strict typing
    def vectorize_multimodal(self, text: str, image_bytes: Optional[bytes] = None) -> list:
        """Generates cross-modal CLIP vectors for text-to-image alignment."""
        # Default text clip alignment vector
        tokens = clip.tokenize([text], truncate=True).to(self.device)
        with torch.no_grad():
            features = self.clip_model.encode_text(tokens)
            features /= features.norm(dim=-1, keepdim=True)
            clip_vector = features.cpu().numpy()[0].tolist()

        if image_bytes:
            try:
                pil_image = Image.open(io.BytesIO(image_bytes))
                # FIX 3: type ignore added because the linter doesn't know clip_preprocess returns a PyTorch Tensor
                image = self.clip_preprocess(pil_image).unsqueeze(0).to(self.device)  # type: ignore
                
                with torch.no_grad():
                    img_features = self.clip_model.encode_image(image)
                    img_features /= img_features.norm(dim=-1, keepdim=True)
                    clip_vector = img_features.cpu().numpy()[0].tolist()
            except Exception as e:
                print(f"⚠️ Image parsing failed, using text clip vector: {e}")

        return clip_vector

def extract_target_entity(query: str) -> str:
    """
    Strips natural language question prefixes while preserving full compound entities.
    Leverages SpaCy NER to prioritize exact Knowledge Graph nodes, 
    falling back to regex for abstract concepts.
    """
    # Process the query in its original casing. 
    # (Converting to lowercase first destroys SpaCy's ability to detect proper nouns).
    doc = nlp(query.strip("? .!"))
    
    # If the AI detects strict Named Entities (e.g., "Albert Einstein", "NASA"),
    # return them immediately as they are canonical Knowledge Graph nodes.
    if doc.ents:
        return " ".join([ent.text.lower() for ent in doc.ents])
    
    # Fallback: Regex stripping for abstract or non-named entity queries 
    clean_query = query.lower().strip()
    
    # Upgraded regex to catch additional auxiliary verbs (do, does, did, why)
    clean_query = re.sub(
        r'^(what|who|where|when|how|why|tell me|show me)\s+(is|are|was|were|do|does|did)?\s*(the|a|an)?\s*', 
        '', 
        clean_query
    )
    
    # Strip trailing punctuation
    clean_query = clean_query.strip("? .!")
    
    return clean_query

def extract_symbolic_graph(query: str) -> Dict[str, Any]:
    """
    Full Symbolic Layer Extraction.
    This breaks down the query into lineage metadata (Entities + Relations),
    allowing Axiom to answer "how" and "why" questions deterministically.
    """
    doc = nlp(query.strip())
    
    return {
        "canonical_target": extract_target_entity(query),
        "named_entities": [ent.text for ent in doc.ents],
        "relations": [token.lemma_ for token in doc if token.pos_ == "VERB"],
        "noun_chunks": [chunk.text for chunk in doc.noun_chunks]
    }