"""
PubMed / NCBI Entrez publication retrieval using the ORCID identifier.

The NCBI E-Utilities support an ORCID-based search via ESearch:
  https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
  ?db=pubmed&term=0000-0002-1825-0097[auid]&retmax=500

Works are then fetched via EFetch in XML format and parsed with the
xml.etree.ElementTree standard-library module (no external deps).

Returns a list of normalised publication dicts.
"""

import logging
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_RETMAX = 500
_BATCH_SIZE = 200


def get_publications_by_orcid(orcid_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve publications from PubMed for the given ORCID.

    :param orcid_id: Clean ORCID string such as '0000-0002-1825-0097'
    :return: List of normalised publication dicts.
    """
    pmids = _esearch(orcid_id)
    if not pmids:
        logger.info("PubMed: no publications found for ORCID %s", orcid_id)
        return []

    publications: List[Dict[str, Any]] = []
    for i in range(0, len(pmids), _BATCH_SIZE):
        batch = pmids[i : i + _BATCH_SIZE]
        publications.extend(_efetch(batch))

    logger.info("PubMed: found %d publications for ORCID %s", len(publications), orcid_id)
    return publications


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _esearch(orcid_id: str) -> List[str]:
    """Return list of PMIDs matching the ORCID author query."""
    params = {
        "db": "pubmed",
        "term": f"{orcid_id}[auid]",
        "retmax": _RETMAX,
        "retmode": "json",
    }
    try:
        resp = requests.get(_ESEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])
    except requests.RequestException as exc:
        logger.warning("PubMed ESearch failed for ORCID %s: %s", orcid_id, exc)
        return []


def _efetch(pmids: List[str]) -> List[Dict[str, Any]]:
    """Fetch and parse PubMed XML records for a list of PMIDs."""
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }
    try:
        resp = requests.get(_EFETCH_URL, params=params, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("PubMed EFetch failed: %s", exc)
        return []

    publications = []
    try:
        root = ET.fromstring(resp.content)
        for article in root.findall(".//PubmedArticle"):
            pub = _parse_article(article)
            if pub:
                publications.append(pub)
    except ET.ParseError as exc:
        logger.warning("PubMed XML parse error: %s", exc)

    return publications


def _parse_article(article: ET.Element) -> Optional[Dict[str, Any]]:
    medline = article.find("MedlineCitation")
    if medline is None:
        return None

    pmid_el = medline.find("PMID")
    pmid = pmid_el.text if pmid_el is not None else None

    art = medline.find("Article")
    if art is None:
        return None

    # Title
    title_el = art.find("ArticleTitle")
    title = _element_text(title_el)
    if not title:
        return None

    # Journal
    journal_el = art.find(".//Journal/Title")
    journal = _element_text(journal_el)

    # Year
    year = _extract_year(art)

    # Authors
    authors = []
    for author in art.findall(".//AuthorList/Author"):
        last = _element_text(author.find("LastName")) or ""
        fore = _element_text(author.find("ForeName")) or ""
        name = f"{fore} {last}".strip()
        if name:
            authors.append(name)

    # Abstract
    abstract_parts = [_element_text(t) for t in art.findall(".//AbstractText") if t is not None]
    abstract = " ".join(p for p in abstract_parts if p) or None

    # DOI
    doi = None
    for id_el in article.findall(".//ArticleIdList/ArticleId"):
        if id_el.get("IdType") == "doi":
            doi = id_el.text
            break

    return {
        "source": "pubmed",
        "title": title.strip(),
        "doi": doi,
        "pmid": pmid,
        "year": year,
        "authors": authors,
        "journal": journal,
        "abstract": abstract,
        "citations": None,
        "type": "journal-article",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
    }


def _element_text(el: Optional[ET.Element]) -> Optional[str]:
    if el is None:
        return None
    return (el.text or "").strip() or None


def _extract_year(art: ET.Element) -> Optional[str]:
    for path in (
        ".//Journal/JournalIssue/PubDate/Year",
        ".//ArticleDate/Year",
        ".//PubMedPubDate[@PubStatus='pubmed']/Year",
    ):
        el = art.find(path)
        if el is not None and el.text:
            return el.text
    return None
