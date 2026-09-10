

# 🧠 Axiom: Neural Search Engine & Knowledge Graph

[![Rust](https://img.shields.io/badge/Engine-Rust-orange?style=flat-square&logo=rust)](https://www.rust-lang.org/)
[![Python](https://img.shields.io/badge/Refinery-Python-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Qdrant](https://img.shields.io/badge/Vector%20DB-Qdrant-red?style=flat-square)](https://qdrant.tech/)
[![Redis](https://img.shields.io/badge/Buffer-Redis-darkred?style=flat-square&logo=redis)](https://redis.io/)
[![DOI](https://img.shields.io/badge/DOI-10.6084/m9.figshare.33514507-blue.svg)]

**Axiom** is an industrial-grade, crash-proof, hybrid neural search engine and knowledge graph pipeline engineered from the metal up. It combines the raw network execution velocity of **Rust** with state-of-the-art AI transformer models in **Python** to ingest, refine, and index millions of domain-specific semantic facts into a local vector space.

---

## 🏗️ System Architecture

Axiom implements an asynchronous **producer-consumer backpressure model** designed for extreme stability, high throughput, and memory safety on local or constrained infrastructure:

```text
       Target URLs / Dumps 
               │
               ▼
 ┌───────────────────────────┐      Async Queue      ┌───────────────────────────┐      Dense Vectors      ┌───────────────────────────┐
 │   Rust Crawler (Spider)   │ ────────────────────> │      Redis Buffer         │ ────────────────────> │    Python AI Refinery     │
 │ (50 Concurrent Workers)   │   (Strict 2GB Cage)   │ (Asynchronous Shock Absorber) │   (FastEmbed / CLIP)    │ (Tokenization & Chunking) │
 └───────────────────────────┘                       └───────────────────────────┘                         └───────────────────────────┘
                                                                                                                      │
                                                                                                                      ▼
                                                                                                           ┌─────────────────────┐
                                                                                                           │    Qdrant Vault     │
                                                                                                           │ (1M+ Verified Facts)│
                                                                                                           └─────────────────────┘

Core Components
The Ingestion Spider (arom-spider/): A high-concurrency multi-threaded web and data spider written in Rust capable of saturating network I/O while filtering out non-text/binary payloads.

The Shock Absorber (Redis): Configured with strict memory bounds (--maxmemory 2gb --maxmemory-policy noeviction) to safely buffer incoming data streams without risking system out-of-memory (OOM) crashes.

The AI Refinery (arom_refinery.py): A Python pipeline utilizing FastEmbed and local transformer architectures to process chunks and calculate high-dimensional dense vectors (text_dense and clip_multimodal).

The Retrieval Core (Qdrant): A high-speed vector index storing over 1,000,000 domain-specific facts, enabling semantic conceptual matching rather than basic keyword lookups.

 Key Engineering Features
Zero Cloud Dependency: Completely self-hosted, running locally with zero commercial API rate limits or recurring costs.

Crash Immunity & Backpressure Regulation: Automatically balances producer velocity against consumer math processing speed.

Hybrid Multimodal Search: Indexes text and semantic features concurrently for cross-modal search queries.

📂 Repository Structure
Code snippet
Axiom-Knowledge-Graph/
├── arom-spider/             # High-performance Rust crawler engine
│   ├── src/                 # Spider core logic and threading models
│   ├── Cargo.toml           # Rust dependencies and configuration
│   └── Cargo.lock           
├── arom_refinery.py         # Python AI vectorization and Qdrant sync pipeline
├── main.py                  # Core system orchestrator
├── axiom_dashboard.py       # Live telemetry and pipeline dashboard
├── axiom_ui.py              # User-facing search interface gateway
├── hydrate_db.py            # Initial storage loader and schema migrator
└── .gitignore               # Production-grade exclusion rules (hides storage/caches)
