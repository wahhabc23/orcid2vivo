from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rdflib import Graph
from orcid2vivo_app.fastapi_service import OrcidService
from orcid2vivo_app.utility import sparql_insert, test_vivo_connection

app = FastAPI(title="ORCID to VIVO Sync API")

# All settings are controlled here on OrcidService directly.
# No environment variables or config file required.
orcid_service = OrcidService(
    vivo_update_endpoint="http://localhost:8081/api/sparqlUpdate",
    vivo_query_endpoint="http://localhost:8081/api/sparqlQuery",
    vivo_username="admin@osp.com",
    vivo_password="123456",
    namespace="http://vivo.mydomain.edu/individual/",
    use_crossref=True,
    use_pubmed=True,
    use_datacite=True,
    # Uncomment and fill in to enable paid sources:
    # scopus_api_key="your-scopus-key",
    # wos_api_key="your-wos-key",
)


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
            test_vivo_connection(
                orcid_service.vivo_update_endpoint,
                orcid_service.config["vivo_username"],
                orcid_service.config["vivo_password"],
            )
        except RuntimeError as conn_err:
            raise HTTPException(
                status_code=503,
                detail=f"VIVO endpoint is unavailable or credentials are invalid: {conn_err}",
            )

        # ------------------------------------------------------------------ #
        # 4. Insert into VIVO via SPARQL Update                               #
        # ------------------------------------------------------------------ #
        sparql_insert(
            graph,
            orcid_service.vivo_update_endpoint,
            orcid_service.config["vivo_username"],
            orcid_service.config["vivo_password"],
        )

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
