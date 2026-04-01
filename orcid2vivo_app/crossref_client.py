"""
Crossref publication retrieval using the ORCID identifier.

Crossref exposes a free REST API that allows filtering works by ORCID:
  https://api.crossref.org/works?filter=orcid:{orcid_id}

No API key is required, but you should set a polite pool User-Agent with a
mailto address:
  https://api.crossref.org/swagger-ui/index.html#/Works/get_works

Returns a list of normalised publication dicts with the keys:
    source, title, doi, pmid, year, authors, journal, abstract, citations
"""

import logging
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.crossref.org/works"
_MAILTO = "orcid2vivo@example.org"  # polite-pool address
_ROWS = 200  # max per page


def get_publications_by_orcid(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve publications from Crossref for the given ORCID.

    :param orcid_id: Clean ORCID string such as '0000-0002-1825-0097'
    :return: List of normalised publication dicts.
    """
    publications: List[Dict[str, Any]] = []
    cursor = "*"

    while True:
        params: Dict[str, Any] = {
            "filter": f"orcid:{orcid_id}",
            "rows": _ROWS,
            "cursor": cursor,
            "mailto": _MAILTO,
        }
        try:
            resp = requests.get(_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Crossref request failed for ORCID %s: %s", orcid_id, exc)
            break

        data = resp.json()
        items = data.get("message", {}).get("items", [])
        if not items:
            break

        for item in items:
            pub = _normalise(item)
            if pub:
                publications.append(pub)

        # Crossref cursor-based pagination
        next_cursor = data.get("message", {}).get("next-cursor")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

    logger.info("Crossref: found %d publications for ORCID %s", len(publications), orcid_id)
    return publications


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_title(item: Dict[str, Any]) -> Optional[str]:
    titles = item.get("title", [])
    return titles[0] if titles else None


def _extract_year(item: Dict[str, Any]) -> Optional[str]:
    for date_field in ("published-print", "published-online", "issued"):
        dp = item.get(date_field, {}).get("date-parts", [[]])
        if dp and dp[0]:
            return str(dp[0][0])
    return None


def _extract_authors(item: Dict[str, Any]) -> List[str]:
    authors = []
    for author in item.get("author", []):
        given = author.get("given", "")
        family = author.get("family", "")
        name = f"{given} {family}".strip()
        if name:
            authors.append(name)
    return authors


def _normalise(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    title = _extract_title(item)
    if not title:
        return None

    return {
        "source": "crossref",
        "title": title.strip(),
        "doi": item.get("DOI"),
        "pmid": None,
        "year": _extract_year(item),
        "authors": _extract_authors(item),
        "journal": _get_container_title(item),
        "abstract": item.get("abstract"),
        "citations": item.get("is-referenced-by-count"),
        "type": item.get("type"),
        "url": item.get("URL"),
    }


def _get_container_title(item: Dict[str, Any]) -> Optional[str]:
    ct = item.get("container-title", [])
    return ct[0] if ct else None
