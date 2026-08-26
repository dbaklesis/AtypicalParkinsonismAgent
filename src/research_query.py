import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from database import get_connection


EVIDENCE_SCORES = {
    "Very high": 5,
    "High": 4,
    "Moderate": 3,
    "Low": 2,
    "Very low": 1,
    "Not applicable": 0,
}


def search_papers(
    condition: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """
    Find the most important completed Greek summaries.

    Only relevant papers with completed Greek summaries
    are returned.
    """

    connection = get_connection()
    cursor = connection.cursor()

    if condition:

        cursor.execute(
            """
            SELECT
                pmid,
                title,
                publication_date,
                condition,
                study_type,
                importance,
                evidence_level,
                confidence,
                relevance_type,
                summary_el,
                key_finding_el,
                why_it_matters_el,
                limitations_el
            FROM papers
            WHERE
                relevant = 1
                AND summary_status = 'completed'
                AND condition = ?
            ORDER BY
                importance DESC,
                publication_date DESC
            LIMIT ?
            """,
            (
                condition,
                limit,
            ),
        )

    else:

        cursor.execute(
            """
            SELECT
                pmid,
                title,
                publication_date,
                condition,
                study_type,
                importance,
                evidence_level,
                confidence,
                relevance_type,
                summary_el,
                key_finding_el,
                why_it_matters_el,
                limitations_el
            FROM papers
            WHERE
                relevant = 1
                AND summary_status = 'completed'
            ORDER BY
                importance DESC,
                publication_date DESC
            LIMIT ?
            """,
            (limit,),
        )

    rows = cursor.fetchall()

    connection.close()

    return [dict(row) for row in rows]


def print_paper(paper: dict) -> None:
    """
    Display one research paper in a readable format.
    """

    print()
    print("-" * 70)

    print(
        f"PMID: {paper['pmid']}"
    )

    print(
        f"Τίτλος: {paper['title']}"
    )

    print(
        f"Κατάσταση: {paper['condition']}"
    )

    print(
        f"Τύπος μελέτης: {paper['study_type']}"
    )

    print(
        f"Σημαντικότητα: "
        f"{paper['importance']}/5"
    )

    print(
        f"Επίπεδο τεκμηρίωσης: "
        f"{paper['evidence_level']}"
    )

    print(
        f"Βαθμός βεβαιότητας AI: "
        f"{paper['confidence']}/5"
    )

    print()

    print("ΠΕΡΙΛΗΨΗ:")
    print(
        paper["summary_el"]
    )

    print()

    print("ΒΑΣΙΚΟ ΕΥΡΗΜΑ:")
    print(
        paper["key_finding_el"]
    )

    print()

    print("ΓΙΑΤΙ ΕΧΕΙ ΣΗΜΑΣΙΑ:")
    print(
        paper["why_it_matters_el"]
    )

    print()

    print("ΠΕΡΙΟΡΙΣΜΟΙ:")
    print(
        paper["limitations_el"]
    )

    print()


def main():

    print()
    print(
        "Atypical Parkinsonism Research Query"
    )
    print("=" * 70)

    print()

    print(
        "Διαθέσιμες κατηγορίες:"
    )

    print(
        "MSA | PSP | CBS | CBD | DLB | Multiple"
    )

    print()

    condition = input(
        "Για ποια κατηγορία θέλεις αποτελέσματα; "
        "(Enter = όλες): "
    ).strip()

    if condition == "":
        condition = None

    papers = search_papers(
        condition=condition,
        limit=5,
    )

    print()

    if not papers:

        print(
            "Δεν βρέθηκαν ολοκληρωμένες ελληνικές "
            "περιλήψεις για αυτή την κατηγορία."
        )

        print()

        return

    print(
        f"Βρέθηκαν {len(papers)} μελέτες."
    )

    for paper in papers:
        print_paper(paper)


if __name__ == "__main__":
    main()