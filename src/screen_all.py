import sys
import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from database import get_connection, save_screening_result
from screening import screen_paper


def main(limit: int = 15):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT pmid, title, abstract, condition
        FROM papers
        WHERE relevant IS NULL OR summary_status = 'pending'
        LIMIT ?
        """,
        (limit,),
    )

    papers = cursor.fetchall()
    connection.close()

    if not papers:
        print("Δεν βρέθηκαν νέα papers για screening.")
        return

    print("\nAtypical Parkinsonism AI Screening")
    print("=" * 70)
    print(f"Screening limit: {limit}")
    print(f"Selected papers: {len(papers)}\n")

    completed = 0
    errors = 0

    for i, paper in enumerate(papers, 1):
        pmid = paper["pmid"]
        paper_dict = dict(paper)
        abstract_text = paper_dict.get("abstract") or ""

        print(f"\n[{i}/{len(papers)}]")
        print(f"PMID: {pmid}")
        print(f"Title: {paper_dict.get('title')}")

        try:
            # Πέρασμα των 2 positional arguments: (paper, abstract)
            result = screen_paper(paper_dict, abstract_text)

            save_screening_result(
                pmid=pmid,
                relevant=result.relevant,
                relevance_type=result.relevance_type,
                condition=result.condition,
                study_type=result.study_type,
                importance=result.importance,
                evidence_level=result.evidence_level,
                confidence=result.confidence,
                reason=result.reason,
            )

            completed += 1
            print("Status: COMPLETED")
            print(f"Relevant: {result.relevant}")
            print(f"Condition: {result.condition}")
            print(f"Importance: {result.importance}/5")

        except Exception as error:
            errors += 1
            print("Status: FAILED")
            print(f"Error: {error}")

    print("\n" + "=" * 70)
    print("SCREENING COMPLETE")
    print("=" * 70)
    print(f"Completed: {completed}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run screening")
    parser.add_argument("--screen-limit", type=int, default=300, help="Limit items for AI screening")
    args = parser.parse_args()
    
    # Διόρθωση: args.screen_limit αντί για args.limit
    main(limit=args.screen_limit)