import httpx
from typing import Optional, Dict, Any

class WikidataKnowledgeGraph:
    def __init__(self, user_agent: str = "AROM-Axiom-Engine/2.0", timeout: float = 5.0):
        self.headers = {"User-Agent": user_agent}
        self.timeout = timeout
        self.sparql_url = "https://query.wikidata.org/sparql"
        self.search_url = "https://www.wikidata.org/w/api.php"

    async def fetch_live_fact(self, entity_name: str) -> Optional[Dict[str, Any]]:
        """
        Dynamically queries the live Wikidata Knowledge Graph for scientific 
        quantities (with units) and general canonical factual claims.
        """
        if not entity_name:
            return None

        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=self.timeout) as client:
                # 1. Resolve Entity ID (e.g., "speed of light" -> Q2111)
                search_params = {
                    "action": "wbsearchentities",
                    "search": entity_name,
                    "language": "en",
                    "format": "json"
                }
                search_res = await client.get(self.search_url, params=search_params)
                search_data = search_res.json()

                if not search_data.get('search'):
                    return None

                entity_id = search_data['search'][0]['id']

                # 2. Comprehensive SPARQL Query (Quantity + Units + General Claims)
                sparql_query = f"""
                SELECT ?propertyLabel ?valLabel ?amount ?unitLabel WHERE {{
                  wd:{entity_id} ?p ?statement .
                  ?statement ?ps ?value .
                  ?property wikibase:claim ?p .
                  ?property wikibase:statementProperty ?ps .
                  
                  OPTIONAL {{
                    ?statement ?psv ?valNode .
                    ?valNode wikibase:quantityAmount ?amount .
                    ?valNode wikibase:quantityUnit ?unit .
                  }}
                  
                  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
                }} LIMIT 1
                """

                data_res = await client.get(
                    self.sparql_url,
                    params={'query': sparql_query, 'format': 'json'}
                )
                
                if data_res.status_code != 200:
                    return None

                bindings = data_res.json().get('results', {}).get('bindings', [])
                if not bindings:
                    return None

                row = bindings[0]
                prop_name = row.get('propertyLabel', {}).get('value', 'Unknown Property')
                
                # Check for unit-aware quantity value
                if 'amount' in row:
                    amount_val = row['amount']['value']
                    unit_val = row.get('unitLabel', {}).get('value', '')
                    # Remove Wikidata entity URI prefix if unit isn't labeled
                    if "http://www.wikidata.org/entity/" in unit_val:
                        unit_val = ""
                    formatted_val = f"{amount_val} {unit_val}".strip()
                else:
                    formatted_val = row.get('valLabel', {}).get('value', '')
                    if "^^" in formatted_val:
                        formatted_val = formatted_val.split("^^")[0]

                return {
                    "property": prop_name,
                    "value": formatted_val,
                    "source_node": f"Wikidata_Node_{entity_id}",
                    "live_uri": f"https://www.wikidata.org/wiki/{entity_id}",
                    "lineage": [{
                        "source_id": "Wikidata_SPARQL_Engine",
                        "uri": f"https://www.wikidata.org/wiki/{entity_id}",
                        "tier": 1,
                        "verification": f"Canonical Entity ID: {entity_id}"
                    }]
                }

        except Exception as e:
            print(f"⚠️ [Wikidata Traversal Error]: {e}")
            return None


# Global instance helper for simple importing
_wikidata_engine = WikidataKnowledgeGraph()

async def fetch_live_fact(entity_name: str) -> Optional[Dict[str, Any]]:
    """Helper wrapper maintaining backward compatibility with existing callers."""
    return await _wikidata_engine.fetch_live_fact(entity_name)