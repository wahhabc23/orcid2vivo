"""
DataCite publication retrieval using the ORCID identifier.

DataCite exposes a REST API:
  https://api.datacite.org/dois?query=creators.nameIdentifiers.nameIdentifier:{orcid_id}
  &page[size]=200&page[cursor]=1

Returns a list of normalised publication dicts.
"""

import logging
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.datacite.org/dois"
_PAGE_SIZE = 200


def get_publications_by_orcid(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve publications from DataCite for the given ORCID.

    :param orcid_id: Clean ORCID string such as '0000-0002-1825-0097'
    :return: List of normalised publication dicts.
    """
    publications: List[Dict[str, Any]] = []
    params: Dict[str, Any] = {
        "query": f"creators.nameIdentifiers.nameIdentifier:{orcid_id}",
        "page[size]": _PAGE_SIZE,
        "page[cursor]": 1,
    }

    while True:
        try:
            resp = requests.get(_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("DataCite request failed for ORCID %s: %s", orcid_id, exc)
            break

        data = resp.json()
        items = data.get("data", [])
        if not items:
            break

        for item in items:
            pub = _normalise(item)
            if pub:
                publications.append(pub)

        # Cursor pagination
        next_link = data.get("links", {}).get("next")
        if not next_link:
            break

        # The next link is a full URL; use it directly
        try:
            resp = requests.get(next_link, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data", [])
            if not items:
                break
            for item in items:
                pub = _normalise(item)
                if pub:
                    publications.append(pub)
            next_link = data.get("links", {}).get("next")
            if not next_link:
                break
            params = {}  # params are embedded in next_link
        except requests.RequestException as exc:
            logger.warning("DataCite pagination request failed: %s", exc)
            break

    logger.info("DataCite: found %d publications for ORCID %s", len(publications), orcid_id)
    return publications


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    attrs = item.get("attributes", {})

    titles = attrs.get("titles", [])
    title = titles[0].get("title") if titles else None
    if not title:
        return None

    # DOI
    doi = attrs.get("doi")

    # Year
    year: Optional[str] = None
    pub_year = attrs.get("publicationYear")
    if pub_year:
        year = str(pub_year)

    # Authors
    authors: List[str] = []
    for creator in attrs.get("creators", []):
        name = creator.get("name") or ""
        given = creator.get("givenName") or ""
        family = creator.get("familyName") or ""
        full = f"{given} {family}".strip() or name.strip()
        if full:
            authors.append(full)

    # Journal / container
    journal: Optional[str] = None
    for rel in attrs.get("relatedItems", []):
        if rel.get("relationType") == "IsPublishedIn":
            journal = rel.get("titles", [{}])[0].get("title")
            break

    # Abstract
    descriptions = attrs.get("descriptions", [])
    abstract: Optional[str] = None
    for desc in descriptions:
        if desc.get("descriptionType") == "Abstract":
            abstract = desc.get("description")
            break

    resource_type = attrs.get("types", {}).get("resourceTypeGeneral", "dataset")

    return {
        "source": "datacite",
        "title": title.strip(),
        "doi": doi,
        "pmid": None,
        "year": year,
        "authors": authors,
        "journal": journal,
        "abstract": abstract,
        "citations": attrs.get("citationCount"),
        "type": resource_type,
        "url": f"https://doi.org/{doi}" if doi else None,
    }
