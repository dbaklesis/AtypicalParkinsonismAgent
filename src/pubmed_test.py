import requests


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


SEARCHES = {
    "MSA": '"multiple system atrophy"',
    "PSP": '"progressive supranuclear palsy"',
    "CBD/CBS": '("corticobasal degeneration" OR "corticobasal syndrome")',
    "DLB": '"dementia with Lewy bodies"',
}


def search_pubmed(query, retmax=10):
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "sort": "date",
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    return data["esearchresult"]["idlist"]


print()
print("Atypical Parkinsonism Research Scan")
print("=" * 40)
print()

all_pmids = set()

for category, query in SEARCHES.items():

    print(f"{category}:")
    print(f"  Query: {query}")

    try:
        pmids = search_pubmed(query, retmax=10)

        print(f"  Records found: {len(pmids)}")

        for pmid in pmids:
            all_pmids.add(pmid)

    except requests.RequestException as exc:
        print(f"  ERROR: {exc}")

    print()

print("-" * 40)
print(f"Total unique records: {len(all_pmids)}")
print()

print("PMIDs:")
for pmid in sorted(all_pmids):
    print(pmid)