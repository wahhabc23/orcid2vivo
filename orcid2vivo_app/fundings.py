from .vivo_namespace import VIVO, OBO, FOAF, VCARD
from rdflib import RDF, RDFS, XSD, Literal
from .utility import add_date, add_date_interval, safe_get


class FundingCrosswalk:
    def __init__(self, identifier_strategy, create_strategy):
        self.identifier_strategy = identifier_strategy
        self.create_strategy = create_strategy

    def crosswalk(self, orcid_profile, person_uri, graph):
        funding_groups = safe_get(orcid_profile, "activities-summary", "fundings", "group") or []
        # Funding
        for funding_group in funding_groups:
            for funding in funding_group.get("funding-summary") or []:
                if funding.get("type") == "GRANT":

                        title = safe_get(funding, "title", "title", "value")
                        grant_uri = self.identifier_strategy.to_uri(VIVO.Grant, {"title": title})
                        # Type
                        graph.add((grant_uri, RDF.type, VIVO.Grant))

                        # Person
                        graph.add((grant_uri, VIVO.relates, person_uri))

                        # Title
                        graph.add((grant_uri, RDFS.label, Literal(title)))

                        # Role
                        role_uri = self.identifier_strategy.to_uri(VIVO.PrincipalInvestigatorRole,
                                                                   {"grant_uri": grant_uri})
                        graph.add((role_uri, RDF.type, VIVO.PrincipalInvestigatorRole))
                        # Inheres in
                        graph.add((role_uri, OBO.RO_0000052, person_uri))
                        graph.add((role_uri, VIVO.relatedBy, grant_uri))

                        # Date interval
                        (start_year, start_month, start_day) = FundingCrosswalk._get_date_parts("start-date", funding)
                        (end_year, end_month, end_day) = FundingCrosswalk._get_date_parts("end-date", funding)

                        add_date_interval(grant_uri, graph, self.identifier_strategy,
                                          add_date(start_year, graph, self.identifier_strategy, start_month, start_day),
                                          add_date(end_year, graph, self.identifier_strategy, end_month, end_day))

                        # Award amount
                        funding_amount = funding.get("amount")
                        if funding_amount is not None:
                            value = funding_amount.get("value")
                            if value is not None:
                                award_amount = "${:,}".format(int(value))
                                graph.add((grant_uri, VIVO.totalAwardAmount, Literal(award_amount)))

                        # Awarded by
                        organization_name = safe_get(funding, "organization", "name")
                        if organization_name:
                            organization_uri = self.identifier_strategy.to_uri(FOAF.Organization,
                                                                               {"name": organization_name})
                            graph.add((grant_uri, VIVO.assignedBy, organization_uri))
                            if self.create_strategy.should_create(FOAF.Organization, organization_uri):
                                graph.add((organization_uri, RDF.type, FOAF.Organization))
                                graph.add((organization_uri, RDFS.label, Literal(organization_name)))

                        # Identifiers
                        external_identifiers = safe_get(funding, "external-ids", "external-id") or []
                        for external_identifier in external_identifiers:
                            if "funding-external-identifier-value" in external_identifier or "external-id-value" in external_identifier:
                                graph.add((grant_uri, VIVO.sponsorAwardId,
                                           Literal(external_identifier.get("external-id-value"))))
                            identifier_url = safe_get(external_identifier, "external-id-url", "value")
                            if identifier_url:
                                vcard_uri = self.identifier_strategy.to_uri(VCARD.Kind, {"url": identifier_url})
                                graph.add((vcard_uri, RDF.type, VCARD.Kind))
                                # Has contact info
                                graph.add((grant_uri, OBO.ARG_2000028, vcard_uri))
                                # Url vcard
                                vcard_url_uri = self.identifier_strategy.to_uri(VCARD.URL, {"vcard_uri": vcard_uri})
                                graph.add((vcard_url_uri, RDF.type, VCARD.URL))
                                graph.add((vcard_uri, VCARD.hasURL, vcard_url_uri))
                                graph.add((vcard_url_uri, VCARD.url, Literal(identifier_url, datatype=XSD.anyURI)))

    @staticmethod
    def _get_date_parts(field_name, funding):
        return safe_get(funding, field_name, "year", "value"), \
               safe_get(funding, field_name, "month", "value"), \
               safe_get(funding, field_name, "day", "value")
