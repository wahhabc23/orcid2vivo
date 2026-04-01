"""
Scopus (Elsevier) publication retrieval using the ORCID identifier.

This is an optional, paid data source.  It will only be called when
USE_SCOPUS=True and SCOPUS_API_KEY is set in the environment / config.

Uses the Scopus Search API:
  https://api.elsevier.com/content/search/scopus
  ?query=ORCID({orcid_id})&apiKey={key}&count=200

Documentation:
  https://dev.elsevier.com/documentation/ScopusSearchAPI.wadl

Returns a list of normalised publication dicts.
"""

import logging
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.elsevier.com/content/search/scopus"
_PAGE_SIZE = 200


def get_publications_by_orcid(
    orcid_id: str, api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve publications from Scopus for the given ORCID.

    :param orcid_id: Clean ORCID string such as '0000-0002-1825-0097'
    :param api_key: Elsevier/Scopus API key.  If None the function returns [].
    :return: List of normalised publication dicts.
    """
    if not api_key:
        logger.warning("Scopus: API key not provided – skipping.")
        return []

    publications: List[Dict[str, Any]] = []
    start = 0

    while True:
        params: Dict[str, Any] = {
            "query": f"ORCID({orcid_id})",
            "apiKey": api_key,
            "count": _PAGE_SIZE,
            "start": start,
            "field": (
                "dc:title,prism:doi,prism:publicationName,prism:coverDate,"
                "author,dc:description,citedby-count,prism:url,subtypeDescription"
            ),
        }
        headers = {"Accept": "application/json"}
        try:
            resp = requests.get(_BASE_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Scopus request failed for ORCID %s: %s", orcid_id, exc)
            break

        data = resp.json()
        results = data.get("search-results", {})
        entries = results.get("entry", [])
        if not entries:
            break

        for entry in entries:
            pub = _normalise(entry)
            if pub:
                publications.append(pub)

        total_results = int(results.get("opensearch:totalResults", 0))
        start += _PAGE_SIZE
        if start >= total_results:
            break

    logger.info("Scopus: found %d publications for ORCID %s", len(publications), orcid_id)
    return publications


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = entry.get("dc:title", "").strip()
    if not title:
        return None

    # Year from cover-date 'YYYY-MM-DD'
    cover_date = entry.get("prism:coverDate", "")
    year = cover_date[:4] if cover_date else None

    # Authors
    authors: List[str] = []
    for author in entry.get("author", []):
        name = author.get("authname", "").strip()
        if name:
            authors.append(name)

    doi = entry.get("prism:doi")

    return {
        "source": "scopus",
        "title": title,
        "doi": doi,
        "pmid": None,
        "year": year,
        "authors": authors,
        "journal": entry.get("prism:publicationName"),
        "abstract": entry.get("dc:description"),
        "citations": _safe_int(entry.get("citedby-count")),
        "type": entry.get("subtypeDescription"),
        "url": entry.get("prism:url"),
    }


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
