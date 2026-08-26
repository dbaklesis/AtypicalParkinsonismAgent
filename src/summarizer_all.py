import sys
from pathlib import Path

# Allow imports from src/
BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from database import get_connection
from summarizer import summarize_paper


def get_pending_summaries(limit: int) -> list[dict]:
    """
    Return papers that are relevant and important enough
    to receive a Greek AI summary.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            pmid,
            title,
            abstract,
            condition,
            importance,
            evidence_level
        FROM papers
        WHERE
            relevant = 1
            AND importance >= 4
            AND (
                summary_status IS NULL
                OR summary_status = 'failed'
            )
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


def mark_processing(pmid: str) -> None:
    """
    Mark a paper as currently being summarized.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE papers
        SET summary_status = ?
        WHERE pmid = ?
        """,
        ("processing", pmid),
    )

    connection.commit()
    connection.close()


def mark_failed(pmid: str) -> None:
    """
    Mark a paper as failed so it can be retried later.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE papers
        SET summary_status = ?
        WHERE pmid = ?
        """,
        ("failed", pmid),
    )

    connection.commit()
    connection.close()


def save_summary(pmid: str, result) -> None:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(papers)")
    columns = {row["name"] for row in cursor.fetchall()}
    if "title_el" not in columns:
        cursor.execute("ALTER TABLE papers ADD COLUMN title_el TEXT")

    cursor.execute(
        """
        UPDATE papers
        SET
            title_el = ?,
            summary_el = ?,
            key_finding_el = ?,
            why_it_matters_el = ?,
            limitations_el = ?,
            summary_status = ?
        WHERE pmid = ?
        """,
        (
            result.title_el,
            result.summary_el,
            result.key_finding_el,
            result.why_it_matters_el,
            result.limitations_el,
            "completed",
            pmid,
        ),
    )

    connection.commit()
    connection.close()


def main(limit: int = 5) -> None:

    print()
    print("Atypical Parkinsonism Greek Summarizer")
    print("=" * 70)
    print()

    papers = get_pending_summaries(limit)

    if not papers:
        print("No papers waiting for Greek summaries.")
        print()
        return

    print(f"Selected papers: {len(papers)}")
    print()

    completed = 0
    failed = 0

    for index, paper in enumerate(papers, start=1):

        pmid = paper["pmid"]

        print(
            f"[{index}/{len(papers)}] "
            f"PMID: {pmid}"
        )

        print(
            f"      Condition: {paper['condition']}"
        )

        print(
            f"      Importance: {paper['importance']}/5"
        )

        print(
            "      Sending to OpenAI..."
        )

        mark_processing(pmid)

        try:

            result = summarize_paper(
                title=paper["title"],
                abstract=paper["abstract"] or "",
            )

            save_summary(
                pmid=pmid,
                result=result,
            )

            completed += 1

            print(
                "      [OK] Completed"
            )

        except Exception as error:

            failed += 1

            mark_failed(pmid)

            print(
                f"      [ERROR] Failed: {error}"
            )
            
        print()

    remaining = len(
        get_pending_summaries(1000000)
    )

    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print()
    print(f"Completed: {completed}")
    print(f"Failed:    {failed}")
    print(f"Remaining: {remaining}")
    print()


if __name__ == "__main__":

    limit = 5

    if len(sys.argv) > 1:

        try:
            limit = int(sys.argv[1])

        except ValueError:
            print(
                "Usage: python src\\summarizer_all.py [limit]"
            )
            raise SystemExit(1)

    if limit <= 0:
        print("Limit must be greater than zero.")
        raise SystemExit(1)

    main(limit)