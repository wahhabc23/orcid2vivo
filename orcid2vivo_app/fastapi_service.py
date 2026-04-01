import logging
from typing import Dict, Any, Optional

# Import the core crosswalk executor without executing the argparse/CLI code
from orcid2vivo import default_execute
from orcid2vivo_app.utility import get_or_create_author_uri
from orcid2vivo_app.publication_aggregator import aggregate_publications
from orcid2vivo_app.external_publications import add_external_publications_to_graph
from orcid2vivo_app.vivo_uri import HashIdentifierStrategy
from orcid2vivo_app import config as app_config

logger = logging.getLogger(__name__)


class OrcidProcessingError(Exception):
    """Custom exception raised when the legacy package fails to process an ORCID."""
    pass


class OrcidService:
    def __init__(
        self,
        use_cache: bool = True,
        timeout: int = 10,
        namespace: Optional[str] = None,
        vivo_query_endpoint: Optional[str] = None,
        vivo_username: Optional[str] = None,
        vivo_password: Optional[str] = None,
    ):
        """
        Initialize the ORCID Service.

        :param use_cache: Whether to use caching (stub concept for future use).
        :param timeout: Timeout for remote requests.
        :param namespace: The base VIVO namespace. Defaults to ``config.VIVO_NAMESPACE``.
        :param vivo_query_endpoint: SPARQL SELECT endpoint used to look up existing
            author URIs.  Defaults to ``config.VIVO_SPARQL_QUERY_ENDPOINT``.
        :param vivo_username: VIVO admin username.  Defaults to ``config.VIVO_USERNAME``.
        :param vivo_password: VIVO admin password.  Defaults to ``config.VIVO_PASSWORD``.
        """
        self.config = {
            "use_cache": use_cache,
            "timeout": timeout,
            "namespace": namespace or app_config.VIVO_NAMESPACE,
            "vivo_query_endpoint": vivo_query_endpoint or app_config.VIVO_SPARQL_QUERY_ENDPOINT,
            "vivo_username": vivo_username or app_config.VIVO_USERNAME,
            "vivo_password": vivo_password or app_config.VIVO_PASSWORD,
        }

    def process_orcid(self, orcid_id: str) -> Dict[str, Any]:
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
                confirmed_orcid_id=False,
            )

            # ------------------------------------------------------------------
            # Step 3 – External publication retrieval & deduplication
            # ------------------------------------------------------------------
            from orcid2vivo_app.utility import clean_orcid
            clean_id = clean_orcid(orcid_id)
            publications = aggregate_publications(clean_id)

            # ------------------------------------------------------------------
            # Step 4 – Add external publications to the graph
            # ------------------------------------------------------------------
            identifier_strategy = HashIdentifierStrategy()
            add_external_publications_to_graph(
                publications=publications,
                person_uri=person_uri,
                graph=graph,
                identifier_strategy=identifier_strategy,
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

        except ValueError as ve:
            logger.warning("Validation error processing %s: %s", orcid_id, ve)
            raise ve
        except OrcidProcessingError:
            raise
        except Exception as e:
            logger.error("Pipeline failed for ORCID %s: %s", orcid_id, str(e))
            raise OrcidProcessingError(f"Internal processing failed: {str(e)}") from e
