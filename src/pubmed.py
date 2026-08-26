import time
import xml.etree.ElementTree as ET

from typing import Optional
from datetime import datetime, timedelta, timezone
import requests

from database import (
    get_connection,
    get_state,
    initialize_database,
    set_state,
)


BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

TIMEOUT = 30

SEARCHES = {
    "MSA": '"multiple system atrophy"',
    "PSP": '"progressive supranuclear palsy"',
    "CBD/CBS": '("corticobasal degeneration" OR "corticobasal syndrome")',
    "DLB": '"dementia with Lewy bodies"',
}


class PubMedError(Exception):
    pass


def utc_now() -> str:
    """
    Return the current UTC timestamp.
    """

    return datetime.now(
        timezone.utc
    ).replace(
        microsecond=0
    ).isoformat()


def search_pubmed(
    query: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    retmax: int = 10000,
) -> list[str]:

    url = f"{BASE_URL}/esearch.fcgi"

    if start_date and end_date:

        query = (
            f"({query}) AND "
            f"{start_date}:{end_date}[pdat]"
        )

    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "sort": "pub_date",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "esearchresult",
            {}
        ).get(
            "idlist",
            []
        )

    except requests.RequestException as exc:

        raise PubMedError(
            f"PubMed search failed: {exc}"
        ) from exc

def fetch_pubmed_records(
    pmids: list[str],
) -> list[dict]:

    if not pmids:
        return []

    url = f"{BASE_URL}/efetch.fcgi"

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=TIMEOUT,
        )

        response.raise_for_status()

    except requests.RequestException as exc:

        raise PubMedError(
            f"PubMed fetch failed: {exc}"
        ) from exc

    try:

        root = ET.fromstring(
            response.text
        )

    except ET.ParseError as exc:

        raise PubMedError(
            "PubMed returned invalid XML."
        ) from exc

    records = []

    for article in root.findall(
        ".//PubmedArticle"
    ):

        record = parse_article(
            article
        )

        if record:
            records.append(record)

    return records


def parse_article(
    article: ET.Element,
) -> Optional[dict]:

    pmid_element = article.find(
        ".//PMID"
    )

    if (
        pmid_element is None
        or not pmid_element.text
    ):
        return None

    pmid = pmid_element.text.strip()

    title_element = article.find(
        ".//ArticleTitle"
    )

    title = ""

    if title_element is not None:

        title = "".join(
            title_element.itertext()
        ).strip()

    abstract_parts = []

    for abstract_text in article.findall(
        ".//Abstract/AbstractText"
    ):

        text = "".join(
            abstract_text.itertext()
        ).strip()

        label = abstract_text.attrib.get(
            "Label"
        )

        if label:
            text = f"{label}: {text}"

        if text:
            abstract_parts.append(text)

    abstract = "\n\n".join(
        abstract_parts
    )

    journal_element = article.find(
        ".//Journal/Title"
    )

    journal = ""

    if (
        journal_element is not None
        and journal_element.text
    ):

        journal = journal_element.text.strip()

    authors = []

    for author in article.findall(
        ".//AuthorList/Author"
    ):

        last_name = author.findtext(
            "LastName",
            default=""
        )

        initials = author.findtext(
            "Initials",
            default=""
        )

        if last_name:

            name = last_name

            if initials:
                name += f" {initials}"

            authors.append(name)

    doi = extract_doi(article)

    publication_date = extract_date(
        article
    )

    return {
        "pmid": pmid,
        "title": title,
        "abstract": abstract,
        "journal": journal,
        "authors": authors,
        "publication_date": publication_date,
        "doi": doi,
        "pubmed_url":
            f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }


def extract_doi(
    article: ET.Element,
) -> str:

    for identifier in article.findall(
        ".//ArticleId"
    ):

        if (
            identifier.attrib.get("IdType")
            == "doi"
        ):

            if identifier.text:
                return identifier.text.strip()

    return ""


def extract_date(
    article: ET.Element,
) -> str:

    year = article.findtext(
        ".//PubDate/Year"
    )

    month = article.findtext(
        ".//PubDate/Month"
    )

    day = article.findtext(
        ".//PubDate/Day"
    )

    if year:

        result = year.strip()

        if month:
            result += f"-{month.strip()}"

        if day:
            result += f"-{day.strip()}"

        return result

    medline_date = article.findtext(
        ".//PubDate/MedlineDate"
    )

    if medline_date:
        return medline_date.strip()

    return ""


def get_existing_pmids(
    pmids: list[str],
) -> set[str]:

    if not pmids:
        return set()

    connection = get_connection()

    placeholders = ",".join(
        "?" for _ in pmids
    )

    cursor = connection.cursor()

    cursor.execute(
        f"""
        SELECT pmid
        FROM papers
        WHERE pmid IN ({placeholders})
        """,
        pmids,
    )

    existing = {
        row["pmid"]
        for row in cursor.fetchall()
    }

    connection.close()

    return existing


def save_record(
    record: dict,
) -> None:

    now = utc_now()

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO papers (
            pmid,
            title,
            abstract,
            journal,
            publication_date,
            doi,
            pubmed_url,
            first_seen,
            last_updated
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(pmid)
        DO UPDATE SET
            title = excluded.title,
            abstract = excluded.abstract,
            journal = excluded.journal,
            publication_date = excluded.publication_date,
            doi = excluded.doi,
            pubmed_url = excluded.pubmed_url,
            last_updated = excluded.last_updated
        """,
        (
            record["pmid"],
            record["title"],
            record["abstract"],
            record["journal"],
            record["publication_date"],
            record["doi"],
            record["pubmed_url"],
            now,
            now,
        ),
    )

    connection.commit()

    connection.close()


def save_topic(
    pmid: str,
    topic: str,
) -> None:

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO paper_topics (
            pmid,
            topic
        )
        VALUES (?, ?)
        """,
        (
            pmid,
            topic,
        ),
    )

    connection.commit()

    connection.close()

def get_scan_start_date() -> str:
    """
    Determine the beginning of the next monitoring window.

    We deliberately overlap the previous scan by two days
    to reduce the chance of missing delayed PubMed records.
    """

    last_scan = get_state(
        "last_successful_scan"
    )

    if not last_scan:

        # Initial scan:
        # retrieve the recent history.
        now = datetime.now(timezone.utc)

        start = now - timedelta(
            days=30
        )

        return start.strftime(
            "%Y/%m/%d"
        )

    try:

        last_datetime = datetime.fromisoformat(
            last_scan
        )

        start = last_datetime - timedelta(
            days=2
        )

        return start.strftime(
            "%Y/%m/%d"
        )

    except ValueError:

        # If the stored state is invalid,
        # fall back safely to a 30-day scan.
        now = datetime.now(timezone.utc)

        start = now - timedelta(
            days=30
        )

        return start.strftime(
            "%Y/%m/%d"
        )


def get_scan_end_date() -> str:
    """
    Return today's UTC date.
    """

    return datetime.now(
        timezone.utc
    ).strftime(
        "%Y/%m/%d"
    )

def run_scan() -> None:

    initialize_database()

    print()
    print(
        "Atypical Parkinsonism Research Agent"
    )
    print("=" * 50)
    print()

    start_date = get_scan_start_date()
    end_date = get_scan_end_date()

    print(
        f"Monitoring period:"
    )

    print(
        f"  {start_date} -> {end_date}"
    )

    print()

    all_pmids = set()

    topic_pmids = {}

    # ----------------------------------------
    # SEARCH
    # ----------------------------------------

    for topic, query in SEARCHES.items():

        print(
            f"Searching {topic}..."
        )

        print(
            f"  Date range: "
            f"{start_date} -> {end_date}"
        )

        pmids = search_pubmed(
            query,
            start_date=start_date,
            end_date=end_date,
        )

        topic_pmids[topic] = set(
            pmids
        )

        all_pmids.update(
            pmids
        )

        print(
            f"  Found {len(pmids)} records"
        )

        time.sleep(0.35)

    print()

    print(
        f"Unique PMIDs found: "
        f"{len(all_pmids)}"
    )

    # ----------------------------------------
    # CHECK DATABASE
    # ----------------------------------------

    existing = get_existing_pmids(
        list(all_pmids)
    )

    new_pmids = (
        all_pmids - existing
    )

    print(
        f"Already in database: "
        f"{len(existing)}"
    )

    print(
        f"New records: "
        f"{len(new_pmids)}"
    )

    print()

    # ----------------------------------------
    # FETCH & SAVE
    # ----------------------------------------

    if new_pmids:

        print(
            "Fetching new records..."
        )

        records = fetch_pubmed_records(
            list(new_pmids)
        )

        print(
            f"Retrieved: "
            f"{len(records)}"
        )

        for record in records:

            save_record(
                record
            )

            for topic, pmids in topic_pmids.items():

                if record["pmid"] in pmids:

                    save_topic(
                        record["pmid"],
                        topic,
                    )

        print(
            "New records saved."
        )

    else:

        print(
            "No new records found."
        )

    # ----------------------------------------
    # UPDATE SCAN STATE
    # ----------------------------------------

    scan_time = utc_now()

    set_state(
        "last_successful_scan",
        scan_time,
    )

    print()

    print(
        f"Last successful scan:"
    )

    print(
        f"  {scan_time}"
    )

    print()

    print(
        "Scan completed."
    )

if __name__ == "__main__":

    try:

        run_scan()

    except PubMedError as exc:

        print()
        print(
            f"ERROR: {exc}"
        )

        raise SystemExit(1)