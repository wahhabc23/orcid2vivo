from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rdflib import Graph
from orcid2vivo_app.fastapi_service import OrcidService
from orcid2vivo_app.utility import sparql_insert, test_vivo_connection
from orcid2vivo_app import config as app_config

app = FastAPI(title="ORCID to VIVO Sync API")

# Instantiate the service once at startup.  Configuration is read from
# environment variables via orcid2vivo_app.config (with the values below as
# hard-coded fallbacks for development convenience).
orcid_service = OrcidService(
    namespace=app_config.VIVO_NAMESPACE,
    vivo_query_endpoint=app_config.VIVO_SPARQL_QUERY_ENDPOINT,
    vivo_username=app_config.VIVO_USERNAME,
    vivo_password=app_config.VIVO_PASSWORD,
)

# VIVO connectivity settings – read from environment / config module.
VIVO_ENDPOINT = app_config.VIVO_ENDPOINT
VIVO_USERNAME = app_config.VIVO_USERNAME
VIVO_PASSWORD = app_config.VIVO_PASSWORD


class SyncRequest(BaseModel):
    orcid_id: str


@app.post("/sync")
def sync_orcid(request: SyncRequest):
    """
    Full ORCID-to-VIVO sync pipeline.

    Workflow
    --------
    1. Run :meth:`OrcidService.process_orcid` to:
       a. Resolve or mint the VIVO author URI for the ORCID.
       b. Crosswalk the ORCID public profile (bio, affiliations, fundings,
          ORCID-listed works) into RDF.
       c. Retrieve publications from all enabled external sources (Crossref,
          PubMed, DataCite, and optionally Scopus / Web of Science).
       d. Merge, deduplicate, and add external publications to the graph.
    2. Parse the Turtle RDF into an rdflib Graph.
    3. Test VIVO connectivity before any data is sent.
    4. Insert the graph into VIVO via SPARQL Update.
    5. Return the success status together with the VIVO author resource URI.
    """
    try:
        # ------------------------------------------------------------------ #
        # 1. Generate the full RDF graph for the given ORCID                  #
        # ------------------------------------------------------------------ #
        result = orcid_service.process_orcid(request.orcid_id)
        author_uri: str = result["person_uri"]

        # ------------------------------------------------------------------ #
        # 2. Parse the Turtle back into an rdflib Graph                       #
        # ------------------------------------------------------------------ #
        graph = Graph()
        graph.parse(data=result["vivo_rdf"], format="turtle")

        # ------------------------------------------------------------------ #
        # 3. Test VIVO connection before attempting insertion                  #
        # ------------------------------------------------------------------ #
        try:
            test_vivo_connection(VIVO_ENDPOINT, VIVO_USERNAME, VIVO_PASSWORD)
        except RuntimeError as conn_err:
            raise HTTPException(
                status_code=503,
                detail=f"VIVO endpoint is unavailable or credentials are invalid: {conn_err}",
            )

        # ------------------------------------------------------------------ #
        # 4. Insert into VIVO via SPARQL Update                               #
        # ------------------------------------------------------------------ #
        sparql_insert(graph, VIVO_ENDPOINT, VIVO_USERNAME, VIVO_PASSWORD)

        # ------------------------------------------------------------------ #
        # 5. Return success + VIVO author resource URI                        #
        # ------------------------------------------------------------------ #
        return {
            "status": "success",
            "message": f"Successfully synced {len(graph)} triples to VIVO.",
            "orcid_id": request.orcid_id,
            "vivo_resource_uri": author_uri,
        }

    except HTTPException:
        # Re-raise FastAPI HTTP exceptions unchanged
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync ORCID: {str(e)}")


# To run this server:
#   source .venv/bin/activate
#   pip install fastapi uvicorn
#   uvicorn example_fastapi_app:app --reload
