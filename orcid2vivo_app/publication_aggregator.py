"""
Publication aggregation pipeline.

Responsibilities
----------------
1. Query all enabled data sources for a given ORCID.
2. Merge the raw result lists.
3. Deduplicate using DOI → PMID → normalised title (in that priority order).
4. Enrich the merged record by filling in missing fields from duplicate entries.

Usage
-----
    from orcid2vivo_app.publication_aggregator import aggregate_publications

    pubs = aggregate_publications("0000-0002-1825-0097")
    # pubs is a list of dicts with keys:
    #   source, title, doi, pmid, year, authors, journal, abstract, citations,
    #   type, url, extra_sources
"""

import logging
import re
import unicodedata
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def aggregate_publications(
    orcid_id: str,
    use_crossref: bool = True,
    use_pubmed: bool = True,
    use_datacite: bool = True,
    scopus_api_key: Optional[str] = None,
    wos_api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Query all enabled sources, merge, and deduplicate publications for *orcid_id*.

    :param orcid_id: Clean ORCID string such as '0000-0002-1825-0097'.
    :param use_crossref: Query Crossref (free, default True).
    :param use_pubmed: Query PubMed/NCBI (free, default True).
    :param use_datacite: Query DataCite (free, default True).
    :param scopus_api_key: Elsevier/Scopus API key. Supplying a non-empty key
        enables Scopus retrieval automatically.
    :param wos_api_key: Clarivate Web of Science API key. Supplying a non-empty
        key enables WoS retrieval automatically.
    :return: Deduplicated list of enriched publication dicts.
    """
    raw: List[Dict[str, Any]] = []

    if use_crossref:
        raw.extend(_safe_fetch("crossref", orcid_id))

    if use_pubmed:
        raw.extend(_safe_fetch("pubmed", orcid_id))

    if use_datacite:
        raw.extend(_safe_fetch("datacite", orcid_id))

    if scopus_api_key:
        raw.extend(_safe_fetch("scopus", orcid_id, api_key=scopus_api_key))

    if wos_api_key:
        raw.extend(_safe_fetch("webofscience", orcid_id, api_key=wos_api_key))

    logger.info(
        "Aggregated %d raw publication records from all sources for ORCID %s",
        len(raw),
        orcid_id,
    )

    deduped = _deduplicate(raw)

    logger.info(
        "After deduplication: %d unique publications for ORCID %s",
        len(deduped),
        orcid_id,
    )
    return deduped


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_fetch(source_name: str, orcid_id: str, **kwargs) -> List[Dict[str, Any]]:
    """Import the client module on demand and call get_publications_by_orcid."""
    try:
        module_map = {
            "crossref": "orcid2vivo_app.crossref_client",
            "pubmed": "orcid2vivo_app.pubmed_client",
            "datacite": "orcid2vivo_app.datacite_client",
            "scopus": "orcid2vivo_app.scopus_client",
            "webofscience": "orcid2vivo_app.webofscience_client",
        }
        import importlib
        module = importlib.import_module(module_map[source_name])
        return module.get_publications_by_orcid(orcid_id, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.error("Source %s raised an error for ORCID %s: %s", source_name, orcid_id, exc)
        return []


def _deduplicate(publications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate a flat list of publication dicts.

    Priority for matching:
      1. DOI  (normalised to lowercase, stripped)
      2. PMID
      3. Normalised title  (lowercase, stripped punctuation/whitespace)

    When a duplicate is found the existing record is enriched with any missing
    fields from the duplicate, and the source name is appended to extra_sources.
    """
    doi_index: Dict[str, int] = {}
    pmid_index: Dict[str, int] = {}
    title_index: Dict[str, int] = {}
    result: List[Dict[str, Any]] = []

    for pub in publications:
        doi = _norm_doi(pub.get("doi"))
        pmid = _norm_pmid(pub.get("pmid"))
        title = _norm_title(pub.get("title"))

        existing_idx: Optional[int] = None
        if doi and doi in doi_index:
            existing_idx = doi_index[doi]
        elif pmid and pmid in pmid_index:
            existing_idx = pmid_index[pmid]
        elif title and title in title_index:
            existing_idx = title_index[title]

        if existing_idx is not None:
            # Enrich the canonical record with any missing fields
            _enrich(result[existing_idx], pub)
        else:
            # New unique publication
            idx = len(result)
            pub["extra_sources"] = []
            result.append(pub)
            if doi:
                doi_index[doi] = idx
            if pmid:
                pmid_index[pmid] = idx
            if title:
                title_index[title] = idx

    return result


def _enrich(canonical: Dict[str, Any], duplicate: Dict[str, Any]) -> None:
    """Fill in missing fields in *canonical* from *duplicate* and record the extra source."""
    for field in ("doi", "pmid", "year", "journal", "abstract", "citations", "url", "type"):
        if not canonical.get(field) and duplicate.get(field):
            canonical[field] = duplicate[field]

    if not canonical.get("authors"):
        canonical["authors"] = duplicate.get("authors", [])

    extra_sources: List[str] = canonical.setdefault("extra_sources", [])
    dup_source = duplicate.get("source", "unknown")
    if dup_source and dup_source not in extra_sources and dup_source != canonical.get("source"):
        extra_sources.append(dup_source)


def _norm_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    return doi.strip().lower()


def _norm_pmid(pmid: Optional[str]) -> Optional[str]:
    if not pmid:
        return None
    return str(pmid).strip()


def _norm_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    # Lowercase, remove accents, strip punctuation, collapse spaces
    nfkd = unicodedata.normalize("NFKD", title.lower())
    ascii_title = nfkd.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^a-z0-9\s]", "", ascii_title)
    return re.sub(r"\s+", " ", cleaned).strip()
