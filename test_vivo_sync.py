import logging
from rdflib import Graph
from orcid2vivo_app.fastapi_service import OrcidService
from orcid2vivo_app.utility import sparql_insert

logging.basicConfig(level=logging.INFO)

def sync_orcid_to_vivo(orcid_id: str):
    # VIVO Configuration Details
    vivo_endpoint = "http://localhost:8081/api/sparqlUpdate"
    username = "admin@osp.com"
    password = "123456"
    name_space = "http://192.168.168.167:8081/individual/"

    print(f"1. Fetching ORCID profile for: {orcid_id}")
    service = OrcidService(namespace=name_space)
    # Ensure this doesn't crash on invalid ORCIDs
    try:
        result = service.process_orcid(orcid_id)
    except Exception as e:
        print(f"Failed to process ORCID: {e}")
        return

    print("2. Parsing resulting RDF data...")
    # The wrapper returns a utf-8 string of Turtle RDF, we can parse it back to a Graph
    # Alternatively, you could modify `fastapi_service.py` to return the `Graph` object directly.
    graph = Graph()
    graph.parse(data=result["vivo_rdf"], format="turtle")

    print(f"3. Attempting to insert {len(graph)} triples to {vivo_endpoint}...")
    try:
        # Note: orcid2vivo_loader.py uses graph_diff to find triples to delete/add.
        # This script just does a pure insert. To do synced updates, you would query 
        # VIVO for the existing graph first, then use rdflib.compare.graph_diff.
        sparql_insert(graph, vivo_endpoint, username, password)
        print("Success! Data loaded to VIVO.")
    except Exception as e:
        print(f"Failed to load into VIVO SPARQL endpoint: {e}")
        print("Note: Check if your VIVO endpoint is actually '/api/sparqlUpdate' or '/vivo/api/sparqlUpdate'.")

if __name__ == "__main__":
    # Test with a public sample ORCID ID
    sync_orcid_to_vivo("0000-0001-9735-2691")
