# orcid2vivo (Python 3 Fork)

This is an unofficial modern Python 3 fork of the original [gwu-libraries/orcid2vivo](https://github.com/gwu-libraries/orcid2vivo) package. 

The original package was written exclusively for Python 2 and relied heavily on CLI/Flask execution. This fork updates the codebase to Python 3, fixes legacy syntax issues, updates dependencies, and—most importantly—exposes the core crosswalk functionality as a clean Python class import for integration into modern backend web frameworks like FastAPI.

## Features
- **Python 3 Compatible**: Fully modernized to run natively on Python 3 (tested via `unittest` up to 3.12).
- **Service Class Wrapper**: Use the `OrcidService` class to retrieve and crosswalk ORCID data directly into memory without triggering old `sys.exit()` paths or `argparse` requirements.
- **FastAPI Ready**: Easily drop the core logic into any asynchronous/synchronous API framework.
- **VIVO Sync**: Includes utilities to push generated RDF graphs directly to a local VIVO SPARQL endpoint.

## Installation and Usage
Dependencies are managed via `requirements.txt` and are compatible with modern package managers like `pip` or `uv`.

```bash
uv venv --python=3.12
source .venv/bin/activate
uv pip install -r requirements.txt
```

## Programmatic Usage Example (FastAPI)
The primary feature of this fork is the ability to use the crosswalk logic inside modern python services. You can import `OrcidService` from `fastapi_service.py`.

Here is a complete example of how to build a FastAPI route that generates VIVO RDF and syncs it to a local endpoint:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rdflib import Graph
from fastapi_service import OrcidService
from orcid2vivo_app.utility import sparql_insert

app = FastAPI(title="ORCID to VIVO Sync API")
orcid_service = OrcidService()

VIVO_ENDPOINT = "http://localhost:8081/api/sparqlUpdate" # sparql update endpoint
VIVO_USERNAME = "[ADMIN_EMAIL_ADDRESS]"
VIVO_PASSWORD = "[PASSWORD]" # Use secure environment variables in production

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
```

To run this server locally:
```bash
pip install fastapi uvicorn
uvicorn example_fastapi_app:app --reload
```

## Original CLI & Testing
The original CLI tools and testing utilities are preserved and updated for Python 3.
You can run the test suite via standard `unittest`:
```bash
python -m unittest discover tests
```

## License
Licensed under the Apache License 2.0. See `LICENSE.txt` for details.
