"""
Configuration for orcid2vivo loaded from environment variables with sane defaults.

Set these in your shell or a .env file (loaded via python-dotenv if installed):

    USE_CROSSREF=True
    USE_PUBMED=True
    USE_DATACITE=True
    USE_SCOPUS=False
    USE_WEB_OF_SCIENCE=False
    SCOPUS_API_KEY=
    WEB_OF_SCIENCE_API_KEY=

    VIVO_ENDPOINT=http://localhost:8081/api/sparqlUpdate
    VIVO_USERNAME=admin@osp.com
    VIVO_PASSWORD=123456

    VIVO_SPARQL_QUERY_ENDPOINT=http://localhost:8081/api/sparqlQuery
    VIVO_NAMESPACE=http://vivo.mydomain.edu/individual/
"""

import os

# ---------------------------------------------------------------------------
# Publication source toggles
# ---------------------------------------------------------------------------
USE_CROSSREF: bool = os.getenv("USE_CROSSREF", "True").lower() in ("1", "true", "yes")
USE_PUBMED: bool = os.getenv("USE_PUBMED", "True").lower() in ("1", "true", "yes")
USE_DATACITE: bool = os.getenv("USE_DATACITE", "True").lower() in ("1", "true", "yes")
USE_SCOPUS: bool = os.getenv("USE_SCOPUS", "False").lower() in ("1", "true", "yes")
USE_WEB_OF_SCIENCE: bool = os.getenv("USE_WEB_OF_SCIENCE", "False").lower() in ("1", "true", "yes")

# ---------------------------------------------------------------------------
# Optional paid-source API keys
# ---------------------------------------------------------------------------
SCOPUS_API_KEY: str = os.getenv("SCOPUS_API_KEY", "")
WEB_OF_SCIENCE_API_KEY: str = os.getenv("WEB_OF_SCIENCE_API_KEY", "")

# ---------------------------------------------------------------------------
# VIVO connectivity
# ---------------------------------------------------------------------------
VIVO_ENDPOINT: str = os.getenv("VIVO_ENDPOINT", "http://localhost:8081/api/sparqlUpdate")
VIVO_USERNAME: str = os.getenv("VIVO_USERNAME", "admin@osp.com")
VIVO_PASSWORD: str = os.getenv("VIVO_PASSWORD", "123456")

# SPARQL SELECT endpoint (used for author URI lookup)
VIVO_SPARQL_QUERY_ENDPOINT: str = os.getenv(
    "VIVO_SPARQL_QUERY_ENDPOINT", "http://localhost:8081/api/sparqlQuery"
)

# ---------------------------------------------------------------------------
# RDF namespace
# ---------------------------------------------------------------------------
VIVO_NAMESPACE: str = os.getenv("VIVO_NAMESPACE", "http://vivo.mydomain.edu/individual/")
