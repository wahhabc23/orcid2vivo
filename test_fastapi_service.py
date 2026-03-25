from orcid2vivo_app.fastapi_service import OrcidService

def main():
    service = OrcidService(use_cache=False)
    # Using a known public ORCID for testing
    test_orcid = "0000-0002-1825-0097"
    
    print(f"Testing OrcidService wrapper with ORCID: {test_orcid}")
    try:
        result = service.process_orcid(test_orcid)
        print("Success! Response keys:", result.keys())
        print("Profile Data Keys:", result["profile_data"].keys())
        # Print a snippet of the RDF
        print("RDF Snippet:", result["vivo_rdf"][:200] + "...")
    except Exception as e:
        print("Error processing ORCID:", e)

if __name__ == "__main__":
    main()
