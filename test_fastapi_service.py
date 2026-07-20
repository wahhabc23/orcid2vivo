from orcid2vivo_app.fastapi_service import OrcidService
from orcid2vivo_app.utility import sparql_insert
from rdflib import Graph
import traceback
import logging

logging.basicConfig(level=logging.INFO)
def main():
    service = OrcidService()
    test_orcid = "0000-0001-9735-2691"
    
    print(f"Testing OrcidService wrapper with ORCID: {test_orcid}")
    try:
        result = service.process_orcid(test_orcid)
        print("Success! RDF generation complete.")
        print("Profile Data Keys:", result["profile_data"].keys())
        print("RDF Snippet:", result["vivo_rdf"][:200] + "...")
        
        print("\nParsing RDF into Graph...")
        graph = Graph()
        graph.parse(data=result["vivo_rdf"], format="turtle")
        
        print("Pushing data to VIVO SPARQL endpoint...")
        sparql_insert(
            graph,
            service.vivo_update_endpoint,
            service.config["vivo_username"],
            service.config["vivo_password"]
        )
        print("Data successfully synced to VIVO!")
        
    except Exception as e:
        traceback.print_exc()

if __name__ == "__main__":
    main()
