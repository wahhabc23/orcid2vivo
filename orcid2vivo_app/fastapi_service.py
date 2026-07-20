import logging
from typing import Dict, Any, Optional

# Import the core crosswalk executor without executing the argparse/CLI code
from orcid2vivo import default_execute
from orcid2vivo_app.utility import get_or_create_author_uri, attach_identity_properties, get_work_uri_by_doi
from orcid2vivo_app.publication_aggregator import aggregate_publications
from orcid2vivo_app.external_publications import add_external_publications_to_graph
from orcid2vivo_app.vivo_uri import HashIdentifierStrategy

logger = logging.getLogger(__name__)


class OrcidProcessingError(Exception):
    """Custom exception raised when the legacy package fails to process an ORCID."""
    pass


class OrcidService:
    def __init__(
        self,
        # ── VIVO connectivity ────────────────────────────────────────────────
        vivo_update_endpoint: str = "http://localhost:8081/api/sparqlUpdate",
        vivo_query_endpoint: str = "http://localhost:8081/api/sparqlQuery",
        vivo_username: str = "admin@osp.com",
        vivo_password: str = "123456",
        namespace: str = "http://vivo.mydomain.edu/individual/",
        confirm_orcid: bool = True,
        # ── Free publication sources ─────────────────────────────────────────
        use_crossref: bool = True,
        use_pubmed: bool = True,
        use_datacite: bool = True,
        # ── Paid publication sources (disabled until key is supplied) ────────
        scopus_api_key: Optional[str] = None,
        wos_api_key: Optional[str] = None,
    ):
        """
        Initialize the ORCID Service.

        All parameters have sensible defaults so the service works out of the
        box against a local VIVO instance.  Override any value when constructing
        the service – no environment variables or config file required.

        :param vivo_update_endpoint: SPARQL Update URL for inserting RDF into VIVO.
        :param vivo_query_endpoint: SPARQL SELECT URL used to look up existing
            author URIs in VIVO.
        :param vivo_username: VIVO admin username.
        :param vivo_password: VIVO admin password.
        :param namespace: Base URI namespace for minting new VIVO individuals.
        :param use_crossref: Query Crossref for publications (free).
        :param use_pubmed: Query PubMed/NCBI for publications (free).
        :param use_datacite: Query DataCite for publications (free).
        :param scopus_api_key: Elsevier/Scopus API key.  Supplying a non-empty
            key automatically enables Scopus retrieval.
        :param wos_api_key: Clarivate Web of Science API key.  Supplying a
            non-empty key automatically enables WoS retrieval.
        """
        self.vivo_update_endpoint = vivo_update_endpoint
        self.config = {
            "namespace": namespace,
            "confirm_orcid": confirm_orcid,
            "vivo_query_endpoint": vivo_query_endpoint,
            "vivo_username": vivo_username,
            "vivo_password": vivo_password,
            "use_crossref": use_crossref,
            "use_pubmed": use_pubmed,
            "use_datacite": use_datacite,
            "scopus_api_key": scopus_api_key or None,
            "wos_api_key": wos_api_key or None,
        }

    def process_orcid(self, orcid_id: str, existing_uri=None, vidwan_id=None, scopus_id=None, wos_id=None, google_scholar_id=None) -> Dict[str, Any]:
        """
        Full ORCID-to-VIVO pipeline.

        Steps
        -----
        1. Resolve or mint the VIVO author URI for *orcid_id*.
        2. Run the core ORCID crosswalk (bio, affiliations, fundings, works from
           the ORCID public API) using the resolved URI.
        3. Aggregate publications from all enabled external sources (Crossref,
           PubMed, DataCite, and optionally Scopus / Web of Science).
        4. Add deduplicated external publications to the RDF graph.
        5. Return the serialised Turtle RDF together with the author URI.

        :param orcid_id: The ORCID identifier string (e.g. ``'0000-0002-1825-0097'``)
        :return: A dictionary with keys ``success``, ``orcid_id``, ``person_uri``,
            ``vivo_rdf``, ``profile_data``, and ``external_publication_count``.
        """
        try:
            namespace = self.config["namespace"]

            # ------------------------------------------------------------------
            # Step 1 – Resolve / mint author URI
            # ------------------------------------------------------------------
            resolved_uri = get_or_create_author_uri(
                orcid_id=orcid_id,
                query_endpoint=self.config["vivo_query_endpoint"],
                username=self.config["vivo_username"],
                password=self.config["vivo_password"],
                namespace=namespace,
                existing_uri=existing_uri,
                update_endpoint=self.vivo_update_endpoint,
            )

            attach_identity_properties(
                uri=resolved_uri,
                update_endpoint=self.vivo_update_endpoint,
                username=self.config["vivo_username"],
                password=self.config["vivo_password"],
                vidwan_id=vidwan_id,
                scopus_id=scopus_id,
                wos_id=wos_id,
                google_scholar_id=google_scholar_id,
            )

            def doi_lookup_fn(doi: str) -> str:
                return get_work_uri_by_doi(
                    doi=doi,
                    query_endpoint=self.config["vivo_query_endpoint"],
                    username=self.config["vivo_username"],
                    password=self.config["vivo_password"],
                )

            # ------------------------------------------------------------------
            # Step 2 – Core ORCID crosswalk (bio, affiliations, fundings, works)
            # ------------------------------------------------------------------
            graph, profile, person_uri = default_execute(
                orcid_id,
                namespace=namespace,
                person_uri=resolved_uri,
                person_id=None,
                skip_person=False,
                person_class=None,
                confirmed_orcid_id=self.config.get("confirm_orcid", True),
                doi_lookup_fn=doi_lookup_fn,
            )

            # ------------------------------------------------------------------
            # Step 3 – External publication retrieval & deduplication
            # ------------------------------------------------------------------
            from orcid2vivo_app.utility import clean_orcid
            clean_id = clean_orcid(orcid_id)
            publications = aggregate_publications(
                clean_id,
                use_crossref=self.config["use_crossref"],
                use_pubmed=self.config["use_pubmed"],
                use_datacite=self.config["use_datacite"],
                scopus_api_key=self.config["scopus_api_key"],
                wos_api_key=self.config["wos_api_key"],
            )

            # ------------------------------------------------------------------
            # Step 4 – Add external publications to the graph
            # ------------------------------------------------------------------
            identifier_strategy = HashIdentifierStrategy()
            add_external_publications_to_graph(
                publications=publications,
                person_uri=person_uri,
                graph=graph,
                identifier_strategy=identifier_strategy,
                doi_lookup_fn=doi_lookup_fn,
            )

            logger.info(
                "Added %d external publications for ORCID %s (graph has %d triples total)",
                len(publications),
                orcid_id,
                len(graph),
            )

            # ------------------------------------------------------------------
            # Step 5 – Serialise
            # ------------------------------------------------------------------
            vivo_rdf_turtle = graph.serialize(format="turtle")
            if isinstance(vivo_rdf_turtle, bytes):
                vivo_rdf_turtle = vivo_rdf_turtle.decode("utf-8")

            return {
                "success": True,
                "orcid_id": orcid_id,
                "person_uri": str(person_uri),
                "vivo_rdf": vivo_rdf_turtle,
                "profile_data": profile,
                "external_publication_count": len(publications),
            }


        except OrcidProcessingError:
            raise
        except Exception as e:
            logger.exception("Pipeline failed for ORCID %s", orcid_id)
            raise OrcidProcessingError(f"Internal processing failed: {str(e)}") from e
