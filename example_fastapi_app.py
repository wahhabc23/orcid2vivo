from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rdflib import Graph
from orcid2vivo_app.fastapi_service import OrcidService
from orcid2vivo_app.utility import sparql_insert

app = FastAPI(title="ORCID to VIVO Sync API")
orcid_service = OrcidService()

# Hardcoded for example purposes. Consider moving to environment variables.
VIVO_ENDPOINT = "http://localhost:8081/api/sparqlUpdate"
VIVO_USERNAME = "admin@osp.com"
VIVO_PASSWORD = "123456"

class SyncRequest(BaseModel):
    orcid_id: str

@app.post("/sync")
def sync_orcid(request: SyncRequest):
    try:
        # 1. Generate the RDF for the given ORCID ID
        result = orcid_service.process_orcid(request.orcid_id)
        
        # 2. Parse the turtle string back to an rdflib Graph
        graph = Graph()
        graph.parse(data=result["vivo_rdf"], format="turtle")
        
        # 3. Publish to VIVO local instance 
        sparql_insert(graph, VIVO_ENDPOINT, VIVO_USERNAME, VIVO_PASSWORD)
        
        return {
            "status": "success",
            "message": f"Successfully synced {len(graph)} triples to VIVO.",
            "orcid_id": request.orcid_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync ORCID: {str(e)}")

# To run this server:
# source .venv/bin/activate
# pip install fastapi uvicorn
# uvicorn example_fastapi_app:app --reload
