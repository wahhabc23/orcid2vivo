"""
Web of Science (Clarivate) publication retrieval using the ORCID identifier.

This is an optional, paid data source.  It will only be called when
USE_WEB_OF_SCIENCE=True and WEB_OF_SCIENCE_API_KEY is set.

Uses the Web of Science Starter API (free-tier) or Expanded API:
  https://api.clarivate.com/apis/wos-starter/v1
  GET /documents?db=WOS&q=AI%3D{orcid_id}&limit=50

Documentation:
  https://developer.clarivate.com/apis/wos-starter

Returns a list of normalised publication dicts.
"""

import logging
from typing import List, Dict, Any, Optional

import requests
from .utility import safe_get

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.clarivate.com/apis/wos-starter/v1/documents"
_PAGE_SIZE = 50  # WoS Starter API maximum per page


def get_publications_by_orcid(
    orcid_id: str, api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieve publications from Web of Science for the given ORCID.

    :param orcid_id: Clean ORCID string such as '0000-0002-1825-0097'
    :param api_key: Clarivate API key.  If None the function returns [].
    :return: List of normalised publication dicts.
    """
    if not api_key:
        logger.warning("Web of Science: API key not provided – skipping.")
        return []

    publications: List[Dict[str, Any]] = []
    page = 1
    headers = {"X-ApiKey": api_key, "Accept": "application/json"}

    while True:
        params: Dict[str, Any] = {
            "db": "WOS",
            "q": f"AI={orcid_id}",
            "limit": _PAGE_SIZE,
            "page": page,
        }
        try:
            resp = requests.get(_BASE_URL, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Web of Science request failed for ORCID %s: %s", orcid_id, exc)
            break

        data = resp.json()
        hits = data.get("hits", [])
        if not hits:
            break

        for hit in hits:
            pub = _normalise(hit)
            if pub:
                publications.append(pub)

        total = data.get("metadata", {}).get("total", 0)
        if len(publications) >= total:
            break
        page += 1

    logger.info("Web of Science: found %d publications for ORCID %s", len(publications), orcid_id)
    return publications


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(hit: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    names = hit.get("names", {})
    title_data = safe_get(hit, "title", "value", default="")
    if not title_data:
        return None

    # Authors
    authors: List[str] = []
    for author in names.get("authors", []):
        display = author.get("displayName", "").strip()
        if display:
            authors.append(display)

    # Year
    pub_info = hit.get("source", {})
    year = str(pub_info.get("publishYear")) if pub_info.get("publishYear") else None

    # DOI
    doi: Optional[str] = None
    for identifier in hit.get("identifiers", {}).get("doi", []):
        doi = identifier.get("value")
        break

    # PMID
    pmid: Optional[str] = None
    for identifier in hit.get("identifiers", {}).get("pmid", []):
        pmid = identifier.get("value")
        break

    return {
        "source": "webofscience",
        "title": title_data.strip(),
        "doi": doi,
        "pmid": pmid,
        "year": year,
        "authors": authors,
        "journal": pub_info.get("sourceTitle"),
        "abstract": safe_get(hit, "abstract", "value"),
        "citations": hit.get("citations", [{}])[0].get("count") if hit.get("citations") and isinstance(hit.get("citations", [{}])[0], dict) else None,
        "type": hit.get("types", [None])[0] if hit.get("types") else None,
        "url": None,
    }
