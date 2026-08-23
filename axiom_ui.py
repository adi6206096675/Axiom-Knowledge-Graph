import streamlit as st
import requests
import urllib.parse

# --- UI Configuration ---
st.set_page_config(
    page_title="Axiom Search",
    page_icon="🌌",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for Axiom Aesthetics ---
st.markdown("""
    <style>
    /* Global Input Styling */
    .stTextInput input {
        font-size: 1.2rem !important;
        padding: 15px !important;
        border-radius: 10px !important;
        border: 1px solid #4a4a4a !important;
        background-color: #0E1117 !important;
        color: white !important;
    }
    
    /* Verified (Modern) Fact Box */
    .fact-box {
        padding: 20px;
        background-color: #161922;
        border-left: 5px solid #00ffcc;
        border-radius: 5px;
        margin-bottom: 20px;
    }
    .fact-value {
        font-size: 2rem;
        font-weight: bold;
        color: #00ffcc;
    }

    /* Casual (Classical) Axiom Cyber-Graph Cards */
    .axiom-card {
        background-color: #12151C;
        border: 1px solid #2A2D34;
        border-left: 4px solid #5ea8ff;
        border-radius: 8px;
        padding: 18px;
        margin-bottom: 15px;
        transition: transform 0.2s ease-in-out;
    }
    .axiom-card:hover {
        border-left: 4px solid #00ffcc;
        background-color: #161922;
    }
    .axiom-badge {
        display: inline-block;
        background-color: #1e222d;
        color: #80DFEA;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-family: monospace;
        letter-spacing: 1px;
        margin-bottom: 10px;
    }
    .axiom-title {
        color: #ffffff;
        font-size: 1.15rem;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .axiom-uri {
        color: #00ffcc;
        font-family: monospace;
        font-size: 0.8rem;
        margin-bottom: 10px;
    }
    .axiom-snippet {
        color: #a0a0a0;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    </style>
""", unsafe_allow_html=True)

# --- Main Header ---
st.title(" Axiom Knowledge Graph")
st.markdown("Query the autonomous multi-modal vector database.")

# --- Search Interface ---
query = st.text_input("", placeholder="Ask a physics or scientific question... (e.g., What is the speed of light?)")

if query:
    with st.spinner("Scanning Qdrant Vector Graph..."):
        try:
            # Safely encode the query using standard urllib
            safe_query = urllib.parse.quote(query)
            
            # Connect to our FastAPI Gateway
            api_url = f"http://127.0.0.1:8001/search?q={safe_query}"
            response = requests.get(api_url, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status", "ERROR")
                
                if status == "VERIFIED_LIVE_FACT":
                    
                    # Create the Dual-Interface Tabs
                    tab_casual, tab_verified = st.tabs(["🏛️ Casual (Classical)", "🎯 Verified (Modern)"])
                    
                    # ---------------------------------------------------------
                    # TAB 1: CASUAL (AXIOM CYBER-GRAPH CARDS)
                    # ---------------------------------------------------------
                    with tab_casual:
                        st.caption(f"Retrieved {len(data.get('all_results', []))} results in {data['metrics']['execution_time_ms']} ms")
                        st.divider()
                        
                        for item in data.get("all_results", []):
                            # Determine column layout based on image presence
                            if item.get('image_url'):
                                col_text, col_img = st.columns([3, 1])
                            else:
                                col_text, col_img = st.columns([1, 0.01]) # Dummy column

                            with col_text:
                                st.markdown(f"""
                                    <div class="axiom-card">
                                        <div class="axiom-badge">[{item['type']}]</div>
                                        <div class="axiom-title">{item['entity']} ➔ {item['value']}</div>
                                        <div class="axiom-uri">{item['uri']}</div>
                                        <div class="axiom-snippet">{item['document']}</div>
                                    </div>
                                """, unsafe_allow_html=True)
                            
                            if item.get('image_url'):
                                with col_img:
                                    st.image(item['image_url'], use_container_width=True)

                    # ---------------------------------------------------------
                    # TAB 2: VERIFIED (MODERN DESIGN)
                    # ---------------------------------------------------------
                    with tab_verified:
                        # 1. Top Level Metrics
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Status", "VERIFIED ✅")
                        col2.metric("Latency", f"{data['metrics']['execution_time_ms']} ms")
                        col3.metric("Property", data.get("property_measured", "N/A"))
                        
                        st.divider()
                        
                        # Render Primary Fact + Optional Image
                        if data.get('image_url'):
                            col_fact, col_primary_img = st.columns([2, 1])
                        else:
                            col_fact, col_primary_img = st.columns([1, 0.01])
                            
                        with col_fact:
                            # 2. The Core Fact
                            st.markdown(f"""
                                <div class="fact-box">
                                    <p style="margin:0; color:#aaaaaa; text-transform:uppercase;">{data.get('entity_resolved', 'UNKNOWN ENTITY')}</p>
                                    <p class="fact-value">{data.get('fact', 'N/A')}</p>
                                </div>
                            """, unsafe_allow_html=True)
                            
                        if data.get('image_url'):
                            with col_primary_img:
                                st.image(data['image_url'], use_container_width=True)
                        
                        # 3. Mathematical Lineage (Traceability)
                        lineage = data.get("all_results", [])
                        if lineage:
                            with st.expander("🔍 View Mathematical Lineage & Context Source"):
                                # Show the top 3 supporting documents for the modern view
                                for item in lineage[:3]:
                                    st.markdown(f"**Source URI:** `{item.get('uri')}`")
                                    st.markdown(f"**Extracted From:**\n> {item.get('document')}")
                                    st.divider()
                                    
                elif status == "UNVERIFIED":
                    st.warning("⚠️ No deterministic consensus found in the Vector Graph for this query.")
                    st.info(f"Reason: {data.get('reason')}")
                else:
                    st.error("Unexpected API response format.")
                    st.json(data)
                    
            else:
                st.error(f"Gateway Error: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            st.error("🚨 Connection Failed: Ensure your FastAPI Gateway (`uvicorn main:app`) is running on port 8001.")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")