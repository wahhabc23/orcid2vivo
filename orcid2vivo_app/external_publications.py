"""
Convert a list of normalised publication dicts (produced by
:mod:`orcid2vivo_app.publication_aggregator`) to VIVO / BIBO RDF triples and
add them to an rdflib :class:`~rdflib.Graph`.

Each publication becomes a ``bibo:Document`` (or a more specific subclass when
the type can be mapped) with:
- ``rdfs:label`` – title
- ``bibo:doi``   – DOI
- ``bibo:pmid``  – PubMed ID
- ``vivo:dateTimeValue`` – year
- ``bibo:abstract`` – abstract
- ``bibo:numCitedBy`` – citation count
- ``vivo:relatedBy`` (Authorship) → the author individual
- ``obo:RO_0000222`` (inheres in) → journal article in journal

The function is intentionally additive – it does NOT clear the graph before
adding new triples.
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional

from rdflib import Graph, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import Namespace

import orcid2vivo_app.vivo_namespace as ns
from orcid2vivo_app.vivo_namespace import VIVO, BIBO, OBO, VCARD, FOAF

logger = logging.getLogger(__name__)

# BIBO may not be defined in the old namespace module – add fallback
if not hasattr(ns, "BIBO"):
    BIBO = Namespace("http://purl.org/ontology/bibo/")

# Map Crossref/DataCite resource types to BIBO classes
_TYPE_MAP: Dict[str, URIRef] = {
    "journal-article": BIBO.AcademicArticle,
    "article": BIBO.AcademicArticle,
    "book": BIBO.Book,
    "book-chapter": BIBO.BookSection,
    "proceedings-article": BIBO.Article,
    "conference-paper": BIBO.Article,
    "dataset": BIBO.Document,
    "report": BIBO.Report,
    "thesis": BIBO.Thesis,
    "preprint": BIBO.Document,
    "posted-content": BIBO.Document,
}


def add_external_publications_to_graph(
    publications: List[Dict[str, Any]],
    person_uri: URIRef,
    graph: Graph,
    identifier_strategy,
    doi_lookup_fn=None,
) -> None:
    """
    Add VIVO/BIBO triples for *publications* to *graph*.

    :param publications: Normalised publication dicts from the aggregator.
    :param person_uri: VIVO URI for the author individual.
    :param graph: Target rdflib Graph (modified in place).
    :param identifier_strategy: Strategy object exposing ``to_uri(clazz, attrs)``.
    :param doi_lookup_fn: Optional function to lookup existing URI by DOI.
    """
    for pub in publications:
        try:
            _add_publication(pub, person_uri, graph, identifier_strategy, doi_lookup_fn)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not add external publication to graph: %s – %s", pub.get("title"), exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _add_publication(
    pub: Dict[str, Any],
    person_uri: URIRef,
    graph: Graph,
    identifier_strategy,
    doi_lookup_fn=None,
) -> None:
    title = pub.get("title") or ""
    if not title:
        return

    doi = pub.get("doi")
    pmid = pub.get("pmid")
    year = pub.get("year")
    journal_name = pub.get("journal")
    abstract = pub.get("abstract")
    citations = pub.get("citations")
    pub_type = (pub.get("type") or "journal-article").lower()
    url = pub.get("url")

    # Determine BIBO class
    bibo_class = _TYPE_MAP.get(pub_type, BIBO.Document)

    # Mint a stable URI for this publication
    pub_attrs = {
        "doi": doi or "",
        "pmid": pmid or "",
        "title": title,
    }
    
    pub_uri_str = None
    if doi and doi_lookup_fn:
        pub_uri_str = doi_lookup_fn(doi)
    
    if pub_uri_str:
        pub_uri = URIRef(pub_uri_str)
    else:
        pub_uri = identifier_strategy.to_uri(BIBO.Document, pub_attrs)

    # Core triples
    graph.add((pub_uri, RDF.type, bibo_class))
    graph.add((pub_uri, RDFS.label, Literal(title, lang="en")))

    if doi:
        graph.add((pub_uri, BIBO.doi, Literal(doi)))
    if pmid:
        graph.add((pub_uri, BIBO.pmid, Literal(str(pmid))))
    if abstract:
        graph.add((pub_uri, BIBO.abstract, Literal(abstract, lang="en")))
    if url:
        graph.add((pub_uri, OWL.sameAs, URIRef(url) if _is_valid_uri(url) else Literal(url)))
    if citations is not None:
        try:
            graph.add((pub_uri, BIBO.numCitedBy, Literal(int(citations), datatype=XSD.integer)))
        except (ValueError, TypeError):
            pass

    # Year
    if year:
        _add_year(pub_uri, year, graph, identifier_strategy)

    # Journal
    if journal_name:
        _add_journal(pub_uri, journal_name, graph, identifier_strategy)

    # Authorship link
    _add_authorship(pub_uri, person_uri, graph, identifier_strategy)


def _add_year(
    pub_uri: URIRef, year: str, graph: Graph, identifier_strategy
) -> None:
    date_uri = identifier_strategy.to_uri(
        VIVO.DateTimeValue, {"year": year, "month": None, "day": None}
    )
    graph.add((date_uri, RDF.type, VIVO.DateTimeValue))
    graph.add((date_uri, VIVO.dateTimePrecision, VIVO.yearPrecision))
    try:
        graph.add(
            (
                date_uri,
                VIVO.dateTime,
                Literal(f"{int(year)}-01-01T00:00:00", datatype=XSD.dateTime),
            )
        )
        graph.add((date_uri, RDFS.label, Literal(str(int(year)))))
    except ValueError:
        graph.add((date_uri, RDFS.label, Literal(year)))
    graph.add((pub_uri, VIVO.dateTimeValue, date_uri))


def _add_journal(
    pub_uri: URIRef, journal_name: str, graph: Graph, identifier_strategy
) -> None:
    journal_uri = identifier_strategy.to_uri(BIBO.Journal, {"name": journal_name})
    graph.add((journal_uri, RDF.type, BIBO.Journal))
    graph.add((journal_uri, RDFS.label, Literal(journal_name, lang="en")))
    graph.add((pub_uri, VIVO.hasPublicationVenue, journal_uri))


def _add_authorship(
    pub_uri: URIRef, person_uri: URIRef, graph: Graph, identifier_strategy
) -> None:
    authorship_uri = identifier_strategy.to_uri(
        VIVO.Authorship, {"pub": str(pub_uri), "person": str(person_uri)}
    )
    graph.add((authorship_uri, RDF.type, VIVO.Authorship))
    graph.add((authorship_uri, VIVO.relates, pub_uri))
    graph.add((authorship_uri, VIVO.relates, person_uri))
    graph.add((pub_uri, VIVO.relatedBy, authorship_uri))
    graph.add((person_uri, VIVO.relatedBy, authorship_uri))


def _is_valid_uri(url: str) -> bool:
    return url.startswith(("http://", "https://", "ftp://"))
