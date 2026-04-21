import logging
from rdflib import RDF, RDFS, XSD, Literal, URIRef, Graph
from .vivo_namespace import VIVO
from numbers import Number
from SPARQLWrapper import SPARQLWrapper, JSON, POST
import re

logger = logging.getLogger(__name__)


def num_to_str(num):
    """
    Converts a number to a string and removes leading 0s.

    If the number is already a string, then just returns.
    """
    if isinstance(num, Number):
        return str(int(num))
    return num.lstrip("0")


def join_if_not_empty(items, sep=" "):
    """
    Joins a list of items with a provided separator.

    Skips an empty item.
    """
    joined = ""
    for item in items:
        if item and len(item) > 0:
            if joined != "":
                joined += sep
            joined += item
    return joined


months = ("January",
          "February",
          "March",
          "April",
          "May",
          "June",
          "July",
          "August",
          "September",
          "October",
          "November",
          "December")


def month_str_to_month_int(month_str):
    """
    Converts a month name to the corresponding month number.

    If already a number, returns the number.

    Also, tries to convert the string to a number.
    """
    if isinstance(month_str, Number):
        return month_str

    try:
        return int(month_str)
    except ValueError:
        pass

    return months.index(month_str)+1


def month_int_to_month_str(month_int):
    if isinstance(month_int, str):
        try:
            month_int = int(month_int)
        except ValueError:
            return month_int

    return months[month_int-1]


def add_date(year, g, identifier_strategy, month=None, day=None, label=None):
    """
    Adds triples for a date.

    Return True if date was added.
    """
    #Date
    date_uri = identifier_strategy.to_uri(VIVO.DateTimeValue, {"year": year, "month": month, "day": day})
    if year:
        g.add((date_uri, RDF.type, VIVO.DateTimeValue))
        #Day, month, and year
        if day and month:
            g.add((date_uri, VIVO.dateTimePrecision, VIVO.yearMonthDayPrecision))
            g.add((date_uri, VIVO.dateTime,
                   Literal("%s-%02d-%02dT00:00:00" % (
                       int(year), month_str_to_month_int(month), int(day)),
                       datatype=XSD.dateTime)))
            g.add((date_uri,
                   RDFS.label,
                   Literal(label or "%s %s, %s" % (month_int_to_month_str(month), num_to_str(day), num_to_str(year)))))
        #Month and year
        elif month:
            g.add((date_uri, VIVO.dateTimePrecision, VIVO.yearMonthPrecision))
            g.add((date_uri, VIVO.dateTime,
                   Literal("%s-%02d-01T00:00:00" % (
                       year, month_str_to_month_int(month)),
                       datatype=XSD.dateTime)))
            g.add((date_uri,
                   RDFS.label,
                   Literal(label or "%s %s" % (month, num_to_str(year)))))
        else:
            #Just year
            g.add((date_uri, VIVO.dateTimePrecision, VIVO.yearPrecision))
            g.add((date_uri, VIVO.dateTime,
                   Literal("%s-01-01T00:00:00" % (
                       year),
                       datatype=XSD.dateTime)))
            g.add((date_uri, RDFS.label, Literal(label or num_to_str(year))))
        return date_uri
    return None


def add_date_interval(subject_uri, g, identifier_strategy, start_uri=None, end_uri=None):
    """
    Adds triples for a date interval.
    """
    if start_uri or end_uri:
        interval_uri = identifier_strategy.to_uri(VIVO.DateTimeInterval, {"subject_uri": subject_uri,
                                                                          "start_uri": start_uri, "end_uri": end_uri})
        g.add((interval_uri, RDF.type, VIVO.DateTimeInterval))
        g.add((subject_uri, VIVO.dateTimeInterval, interval_uri))
        if start_uri:
            g.add((interval_uri, VIVO.start, start_uri))
        if end_uri:
            g.add((interval_uri, VIVO.end, end_uri))
        return interval_uri
    return None


def sparql_insert(graph, endpoint, username, password):
    #Need to construct query
    ns_lines = []
    triple_lines = []
    for line in graph.serialize(format="turtle").splitlines():
        if line.startswith("@prefix"):
            #Change from @prefix to PREFIX
            ns_lines.append("PREFIX" + line[7:-2])
        else:
            triple_lines.append(line)
    query = "\n".join(ns_lines)
    query += "\nINSERT DATA { GRAPH <http://vitro.mannlib.cornell.edu/default/vitro-kb-2> {\n"
    query += "\n".join(triple_lines)
    query += "\n}}"
    sparql_update(query, endpoint, username, password)


def sparql_delete(graph, endpoint, username, password):
    #Need to construct query
    ns_lines = []
    triple_lines = []
    for line in graph.serialize(format="turtle").splitlines():
        if line.startswith("@prefix"):
            #Change from @prefix to PREFIX
            ns_lines.append("PREFIX" + line[7:-2])
        else:
            triple_lines.append(line)
    query = "\n".join(ns_lines)
    query += "\nDELETE DATA { GRAPH <http://vitro.mannlib.cornell.edu/default/vitro-kb-2> {\n"
    query += "\n".join(triple_lines)
    query += "\n}}"
    sparql_update(query, endpoint, username, password)


def sparql_update(query, endpoint, username, password):
    """
    Perform a SPARQL Update query.

    :param query: the query to perform
    :param endpoint: the URL for SPARQL Update on the SPARQL server
    :param username: username for SPARQL Update
    :param password: password for SPARQL Update
    """
    sparql = SPARQLWrapper(endpoint)
    sparql.addParameter("email", username)
    sparql.addParameter("password", password)
    sparql.setQuery(query)
    sparql.setMethod("POST")
    sparql.query()


def clean_orcid(value):
    """
    Minimal ORCID validation.  Allowing for orcid.org/
    """
    if value.find('orcid.org/') > -1:
        return value.split('/')[-1]
    else:
        return value


def is_valid_orcid(orcid):
    """
    Returns true if has correct syntax for an orcid.
    """
    # 0000-0003-1527-0030
    if re.match(r"\d\d\d\d-\d\d\d\d-\d\d\d\d-\d\d\d[0-9X]$", orcid):
        return True
    return False


# ---------------------------------------------------------------------------
# VIVO connectivity helpers
# ---------------------------------------------------------------------------

def test_vivo_connection(endpoint: str, username: str, password: str) -> bool:
    """
    Test whether a VIVO SPARQL Update endpoint is reachable and credentials
    are accepted.

    The function issues a no-op SPARQL Update (inserting an empty graph) and
    checks that no HTTP error is raised.  Any failure (connection error, bad
    credentials, wrong endpoint) will be caught and logged.

    :param endpoint: SPARQL Update URL, e.g.
        ``http://localhost:8081/api/sparqlUpdate``
    :param username: VIVO admin e-mail / username.
    :param password: VIVO admin password.
    :return: ``True`` if the connection and credentials are valid.
    :raises RuntimeError: if the endpoint is unreachable or credentials are
        rejected.
    """
    noop_query = "INSERT DATA { GRAPH <http://vitro.mannlib.cornell.edu/default/vitro-kb-2> { } }"
    try:
        sparql = SPARQLWrapper(endpoint)
        sparql.addParameter("email", username)
        sparql.addParameter("password", password)
        sparql.setQuery(noop_query)
        sparql.setMethod("POST")
        sparql.query()
        logger.info("VIVO connection test succeeded for endpoint %s", endpoint)
        return True
    except Exception as exc:  # noqa: BLE001
        msg = f"VIVO connection test failed for {endpoint}: {exc}"
        logger.error(msg)
        raise RuntimeError(msg) from exc


def get_or_create_author_uri(
    orcid_id: str,
    query_endpoint: str,
    username: str,
    password: str,
    namespace: str = "http://vivo.mydomain.edu/individual/",
    existing_uri: str = None,
    update_endpoint: str = None,
) -> str:
    """
    Return the VIVO individual URI associated with *orcid_id*.

    First queries VIVO via SPARQL SELECT to see whether an individual already
    has ``vivo:orcidId <http://orcid.org/{orcid_id}>``.  If found that URI is
    returned directly.  Otherwise a new URI is minted using the same
    :class:`~orcid2vivo_app.vivo_uri.HashIdentifierStrategy` used by the rest
    of the package.

    :param orcid_id: Clean ORCID string such as ``'0000-0002-1825-0097'``.
    :param query_endpoint: SPARQL SELECT endpoint URL, e.g.
        ``http://localhost:8081/api/sparqlQuery``.
    :param username: VIVO admin e-mail / username.
    :param password: VIVO admin password.
    :param namespace: Base VIVO namespace for minting new URIs.
    :param existing_uri: An existing URI to use. If provided, the ORCID will be attached to it.
    :param update_endpoint: SPARQL Update URL for attaching the ORCID to an existing URI.
    :return: Absolute URI string for the author individual.
    """
    if existing_uri:
        logger.info("Using existing URI %s and attaching ORCID %s", existing_uri, orcid_id)
        endpoint = update_endpoint or query_endpoint.replace("sparqlQuery", "sparqlUpdate").replace("query", "update")
        orcid_uri = f"http://orcid.org/{orcid_id}"
        update_query = (
            "PREFIX vivo: <http://vivoweb.org/ontology/core#>\n"
            "WITH <http://vitro.mannlib.cornell.edu/default/vitro-kb-2>\n"
            "DELETE {\n"
            f"  <{existing_uri}> vivo:orcidId ?oldOrcid .\n"
            "}\n"
            "INSERT {\n"
            f"  <{existing_uri}> vivo:orcidId <{orcid_uri}> .\n"
            "}\n"
            "WHERE {\n"
            f"  OPTIONAL {{ <{existing_uri}> vivo:orcidId ?oldOrcid . }}\n"
            "}"
        )
        try:
            sparql_update(update_query, endpoint, username, password)
            logger.info("Attached ORCID %s to existing URI %s", orcid_id, existing_uri)
        except Exception as exc:
            logger.warning("Could not attach ORCID to existing URI: %s", exc)
        return existing_uri

    orcid_uri = f"http://orcid.org/{orcid_id}"
    ask_query = (
        "PREFIX vivo: <http://vivoweb.org/ontology/core#>\n"
        "SELECT ?person WHERE {\n"
        f"  ?person vivo:orcidId <{orcid_uri}> .\n"
        "} LIMIT 1"
    )
    try:
        sparql = SPARQLWrapper(query_endpoint)
        sparql.addParameter("email", username)
        sparql.addParameter("password", password)
        sparql.setQuery(ask_query)
        sparql.setReturnFormat(JSON)
        sparql.setMethod(POST)
        results = sparql.query().convert()
        bindings = results.get("results", {}).get("bindings", [])
        if bindings:
            existing_uri = bindings[0].get("person", {}).get("value")
            if existing_uri:
                logger.info(
                    "Found existing VIVO URI %s for ORCID %s", existing_uri, orcid_id
                )
                return existing_uri
    except Exception as exc:  # noqa: BLE001
        # Non-fatal – fall through to mint a new URI
        logger.warning(
            "Could not query VIVO for existing URI (ORCID %s): %s – "
            "a new URI will be minted.",
            orcid_id,
            exc,
        )

    # Mint a new URI using the same strategy as the rest of the package
    from .vivo_uri import HashIdentifierStrategy
    from . import vivo_namespace as ns
    from rdflib.namespace import Namespace

    # Temporarily switch the data namespace to the requested one so the
    # minted URI lands in the right namespace.
    original_d = ns.D
    ns.D = Namespace(namespace)
    ns.ns_manager.bind("d", ns.D, replace=True)

    strategy = HashIdentifierStrategy()
    from .vivo_namespace import FOAF
    new_uri = str(strategy.to_uri(FOAF.Person, {"id": orcid_id}))

    # Restore original namespace
    ns.D = original_d
    ns.ns_manager.bind("d", ns.D, replace=True)

    logger.info("Minted new VIVO URI %s for ORCID %s", new_uri, orcid_id)
    return new_uri


def attach_identity_properties(
    uri: str,
    update_endpoint: str,
    username: str,
    password: str,
    vidwan_id: str = None,
    scopus_id: str = None,
    wos_id: str = None,
    google_scholar_id: str = None,
):
    """
    Attaches identity properties to an existing URI in VIVO.
    Any existing values for the provided properties will be removed first
    to avoid duplication.
    """
    properties = []
    if scopus_id:
        properties.append(("<http://vivoweb.org/ontology/core#scopusId>", scopus_id))
    if wos_id:
        properties.append(("<http://vivoweb.org/ontology/core#researcherId>", wos_id))
    if google_scholar_id:
        properties.append(("<http://aufait.com/ontology#googleScholarId>", google_scholar_id))
    if vidwan_id:
        properties.append(("<http://aufait.com/ontology#vidwanId>", vidwan_id))

    if not properties:
        return

    deletes = []
    inserts = []
    optionals = []

    for i, (prop, value) in enumerate(properties):
        var_name = f"?oldVal{i}"
        deletes.append(f"  <{uri}> {prop} {var_name} .")
        optionals.append(f"  OPTIONAL {{ <{uri}> {prop} {var_name} . }}")
        
        safe_val = str(value).replace('"', '\\"')
        inserts.append(f'  <{uri}> {prop} "{safe_val}" .')

    delete_str = "\n".join(deletes)
    insert_str = "\n".join(inserts)
    optional_str = "\n".join(optionals)

    update_query = (
        "WITH <http://vitro.mannlib.cornell.edu/default/vitro-kb-2>\n"
        "DELETE {\n"
        f"{delete_str}\n"
        "}\n"
        "INSERT {\n"
        f"{insert_str}\n"
        "}\n"
        "WHERE {\n"
        f"{optional_str}\n"
        "}"
    )

    try:
        sparql_update(update_query, update_endpoint, username, password)
        logger.info("Attached identity properties to URI %s", uri)
    except Exception as exc:
        logger.warning("Could not attach identity properties to URI %s: %s", uri, exc)


def create_author_uri(
    unique_id: str, 
    query_endpoint: str, 
    username: str, 
    password: str, 
    namespace: str = "http://vivo.mydomain.edu/individual/",
    update_endpoint: str = None
) -> str:
    """
    Creates an author in VIVO and returns the minted URI.
    """
    from .vivo_uri import HashIdentifierStrategy
    from . import vivo_namespace as ns
    from rdflib.namespace import Namespace
    from .vivo_namespace import FOAF

    original_d = ns.D
    ns.D = Namespace(namespace)
    ns.ns_manager.bind("d", ns.D, replace=True)

    strategy = HashIdentifierStrategy()
    new_uri = str(strategy.to_uri(FOAF.Person, {"id": unique_id}))

    ns.D = original_d
    ns.ns_manager.bind("d", ns.D, replace=True)

    logger.info("Minted new VIVO URI %s for unique_id %s", new_uri, unique_id)
    
    endpoint = update_endpoint or query_endpoint.replace("sparqlQuery", "sparqlUpdate").replace("query", "update")
    insert_query = (
        "PREFIX foaf: <http://xmlns.com/foaf/0.1/>\n"
        "INSERT DATA { GRAPH <http://vitro.mannlib.cornell.edu/default/vitro-kb-2> {\n"
        f"  <{new_uri}> a foaf:Person .\n"
        "} }"
    )
    try:
        sparql_update(insert_query, endpoint, username, password)
        logger.info("Created author in VIVO with URI %s", new_uri)
    except Exception as exc:
        logger.warning("Could not create author in VIVO: %s", exc)

    return new_uri