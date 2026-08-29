import requests
import logging
from typing import List, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Europe PMC REST API Endpoint
EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

import requests
import logging
import time
from typing import List, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

EUROPE_PMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

def get_retrying_session(retries=5, backoff_factor=3):
    """
    Session with exponential backoff for handling 503 / 429 server overloads.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,  # Waits 3s, 6s, 12s, 24s
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def build_query(days_back: int = 8) -> str:
    diseases = '("multiple system atrophy" OR "progressive supranuclear palsy" OR "corticobasal degeneration" OR "corticobasal syndrome" OR "dementia with Lewy bodies")'
    return f'{diseases} AND (FIRST_PDATE:[NOW-{days_back}DAYS TO NOW])'

def fetch_europe_pmc_papers(days_back: int = 8, pageSize: int = 50) -> List[Dict[str, Any]]:
    query = build_query(days_back=days_back)
    
    params = {
        "query": query,
        "format": "json",
        "pageSize": pageSize,
        "resultType": "core",
        "synonym": "true"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AtypicalParkinsonismAgent/1.0"
    }

    session = get_retrying_session()

    try:
        response = session.get(EUROPE_PMC_URL, params=params, headers=headers, timeout=45)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("resultList", {}).get("result", [])
        parsed_papers = []

        for item in results:
            raw_id = item.get("pmid") or item.get("id")
            title = item.get("title", "").rstrip(".")
            abstract = item.get("abstractText", "")
            pub_type = item.get("pubType", "")
            journal = item.get("journalTitle", "Unknown Journal")
            
            is_preprint = item.get("source") == "PPR" or "preprint" in str(pub_type).lower()

            if raw_id and title and abstract:
                clean_id = str(raw_id).replace("EPMC_", "")
                parsed_papers.append({
                    "pmid": f"EPMC_{clean_id}",
                    "title": title,
                    "abstract": abstract,
                    "condition": "Atypical Parkinsonism",
                    "source": "Europe PMC (Preprint)" if is_preprint else "Europe PMC",
                    "journal": journal,
                    "pub_date": item.get("firstPublicationDate", "")
                })

        logging.info(f"[Europe PMC] Fetched {len(parsed_papers)} records.")
        return parsed_papers

    except Exception as err:
        logging.error(f"[ERROR] Europe PMC API request failed: {err}")
        return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    papers = fetch_europe_pmc_papers(days_back=10, pageSize=10)
    for p in papers[:2]:
        print(f"\nID: {p['pmid']}\nTitle: {p['title']}\nSource: {p['source']}\nAbstract: {p['abstract'][:150]}...")