import os
from openai import OpenAI
from dotenv import load_dotenv

from database import get_connection


# ============================================================
# INITIALIZATION
# ============================================================

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("OPENAI_API_KEY was not found in .env")

client = OpenAI(api_key=api_key)


# ============================================================
# CONFIGURATION
# ============================================================

MODEL = "gpt-4o"

# Πόσα candidate papers θα πάρουμε αρχικά από τη βάση
CANDIDATE_LIMIT = 15

# Πόσα papers το πολύ θα δοθούν στην τελική απάντηση
FINAL_PAPER_LIMIT = 6

# Ελάχιστο relevance score για να θεωρηθεί ένα paper χρήσιμο
MIN_RELEVANCE_SCORE = 5


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
Είσαι ο ερευνητικός βοηθός για την άτυπη παρκινσονική νόσο.

Ο χρήστης διαβάζει μόνο ελληνικά.
Όλες οι απαντήσεις σου πρέπει να είναι στα ελληνικά.

Η ερευνητική βάση αφορά κυρίως:

- MSA = Πολλαπλή συστηματική ατροφία
- PSP = Προϊούσα υπερπυρηνική παράλυση
- CBS = Φλοιοβασικό σύνδρομο
- CBD = Φλοιοβασική εκφύλιση
- DLB = Άνοια με σωμάτια Lewy

Ο χρήστης μπορεί να χρησιμοποιεί είτε την ελληνική ονομασία
είτε το αγγλικό ακρωνύμιο.

Σημαντικοί κανόνες:

1. Χρησιμοποίησε ΜΟΝΟ τις πληροφορίες που περιλαμβάνονται
   στα papers που σου παρέχονται.

2. Μην επινοείς αποτελέσματα, θεραπείες ή συμπεράσματα.

3. Αν τα διαθέσιμα papers δεν επαρκούν για να απαντήσεις,
   πες το καθαρά.

4. Να ξεχωρίζεις πάντα:
   - τι έδειξε η μελέτη
   - τι σημαίνει αυτό
   - τι ΔΕΝ έχει αποδειχθεί

5. Να μην παρουσιάζεις μια ερευνητική υπόθεση ως αποδεδειγμένη
   θεραπεία ή διάγνωση.

6. Να λαμβάνεις υπόψη το επίπεδο τεκμηρίωσης και τη
   σημαντικότητα κάθε μελέτης.

7. Οι πληροφορίες αφορούν ερευνητική βιβλιογραφία και όχι
   εξατομικευμένη ιατρική συμβουλή.

8. Να γράφεις απλά και κατανοητά ελληνικά, αποφεύγοντας
   περιττή επιστημονική ορολογία.

9. Όταν αναφέρεις συγκεκριμένη μελέτη, να αναφέρεις το PMID.

10. Αν υπάρχουν αντικρουόμενα ή αβέβαια αποτελέσματα,
    να το επισημαίνεις.

11. Μην χρησιμοποιείς πληροφορίες από τη γενική σου γνώση
    που δεν υπάρχουν στα papers που σου παρέχονται.

12. Αν η ερώτηση δεν αφορά την ερευνητική βάση του
    άτυπου παρκινσονισμού, μην προσπαθήσεις να την απαντήσεις
    χρησιμοποιώντας άσχετες μελέτες.

13. Αν η ερώτηση αφορά σύγκριση μεταξύ δύο παθήσεων,
    χρησιμοποίησε μόνο στοιχεία που επιτρέπουν πραγματική
    σύγκριση. Μην θεωρείς ότι επειδή ένα χαρακτηριστικό
    αναφέρεται στη μία πάθηση ισχύει και για την άλλη.

14. Όταν η ερώτηση ζητά "τι καινούργιο υπάρχει",
    δώσε προτεραιότητα στις πιο πρόσφατες σημαντικές μελέτες,
    αλλά μην θυσιάζεις το επίπεδο τεκμηρίωσης.

15. Αν μια μελέτη είναι πρωτόκολλο ή μελλοντική μελέτη
    χωρίς αποτελέσματα, να το αναφέρεις ξεκάθαρα.

16. Μην αναφέρεις άσχετα papers απλώς και μόνο επειδή
    εμφανίστηκαν στα αποτελέσματα αναζήτησης.

17. Αν δεν υπάρχουν αρκετά σχετικά papers, είναι προτιμότερο
    να το πεις καθαρά παρά να χρησιμοποιήσεις άσχετες μελέτες.
"""


# ============================================================
# QUESTION INTERPRETATION
# ============================================================

def interpret_question(
    question: str,
) -> dict:

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": """
Είσαι μηχανισμός ανάλυσης ερωτήσεων για ερευνητική βάση
άτυπου παρκινσονισμού.

Δεν πρέπει να απαντήσεις στην ερώτηση.

Πρέπει μόνο να την ταξινομήσεις και να δημιουργήσεις
χρήσιμους όρους αναζήτησης.

------------------------------------------------------------
1. relevant
------------------------------------------------------------

Χρησιμοποίησε:

relevant=yes

όταν η ερώτηση αφορά:

- MSA
- PSP
- CBS
- CBD
- DLB
- άτυπο παρκινσονισμό
- Parkinson-plus syndromes
- συμπτώματα
- διάγνωση
- θεραπεία
- βιοδείκτες
- πρόγνωση
- παθολογία
- γενετική
- αποκατάσταση
- βάδιση
- cognition
- κλινικά χαρακτηριστικά

σε σχέση με τις παραπάνω παθήσεις.

Χρησιμοποίησε:

relevant=no

όταν η ερώτηση αφορά άσχετη πάθηση ή άσχετο θέμα.

------------------------------------------------------------
2. conditions
------------------------------------------------------------

Επέστρεψε μία ή περισσότερες από:

MSA
PSP
CBS
CBD
DLB
Multiple

ή:

None

------------------------------------------------------------
3. topic
------------------------------------------------------------

Χρησιμοποίησε μία από:

treatment
diagnosis
biomarker
imaging
rehabilitation
prognosis
genetics
pathology
gait
cognition
symptoms
epidemiology
clinical_features

ή:

None

------------------------------------------------------------
4. question_type
------------------------------------------------------------

Χρησιμοποίησε μία από:

general
treatment
diagnosis
comparison
biomarker
prognosis
research
other

------------------------------------------------------------
5. search_mode
------------------------------------------------------------

Χρησιμοποίησε:

recent
standard

------------------------------------------------------------
6. search_terms
------------------------------------------------------------

Δημιούργησε από 3 έως 8 σύντομους αγγλικούς όρους
ή φράσεις που μπορούν να χρησιμοποιηθούν για αναζήτηση
σε τίτλους, περιλήψεις και ερευνητικές περιλήψεις.

------------------------------------------------------------
FORMAT
------------------------------------------------------------

Επέστρεψε ΑΚΡΙΒΩΣ τις παρακάτω γραμμές:

relevant=<yes/no>
conditions=<value>
topic=<value>
question_type=<value>
search_mode=<value>
search_terms=<term1, term2, term3>

Μην γράψεις τίποτα άλλο.
""",
            },
            {
                "role": "user",
                "content": question,
            },
        ],
    )

    text = response.choices[0].message.content.strip()

    result = {
        "relevant": False,
        "conditions": [],
        "topic": None,
        "question_type": "general",
        "search_mode": "standard",
        "search_terms": [],
    }

    for line in text.splitlines():

        line = line.strip()

        if line.startswith("relevant="):

            value = line.split("=", 1)[1].strip().lower()
            result["relevant"] = (value == "yes")

        elif line.startswith("conditions="):

            value = line.split("=", 1)[1].strip()

            if value != "None":
                result["conditions"] = [
                    item.strip()
                    for item in value.split(",")
                    if item.strip()
                ]

        elif line.startswith("topic="):

            value = line.split("=", 1)[1].strip()

            if value != "None":
                result["topic"] = value

        elif line.startswith("question_type="):

            value = line.split("=", 1)[1].strip()
            result["question_type"] = value

        elif line.startswith("search_mode="):

            value = line.split("=", 1)[1].strip()
            result["search_mode"] = value

        elif line.startswith("search_terms="):

            value = line.split("=", 1)[1].strip()

            if value:
                result["search_terms"] = [
                    item.strip()
                    for item in value.split(",")
                    if item.strip()
                ]

    return result


# ============================================================
# DATABASE SEARCH
# ============================================================

def get_candidate_papers(
    conditions: list[str] | None = None,
    search_terms: list[str] | None = None,
    search_mode: str = "standard",
    limit: int = CANDIDATE_LIMIT,
) -> list[dict]:

    connection = get_connection()
    cursor = connection.cursor()

    # Φέρνουμε όλα τα περασμένα από screening papers για τις ζητούμενες παθήσεις
    query = """
        SELECT
            pmid,
            title,
            abstract,
            condition,
            study_type,
            importance,
            evidence_level,
            confidence,
            summary_el,
            key_finding_el,
            why_it_matters_el,
            limitations_el,
            publication_date
        FROM papers
        WHERE
            relevant = 1
            AND screening_status = 'completed'
    """
    
    parameters = []

    if conditions and "Multiple" not in conditions:
        placeholders = ", ".join(["?"] * len(conditions))
        query += f" AND (condition IN ({placeholders}) OR condition = 'Multiple')"
        parameters.extend(conditions)

    if search_mode == "recent":
        query += " ORDER BY publication_date DESC, importance DESC"
    else:
        query += " ORDER BY importance DESC, publication_date DESC"

    query += " LIMIT ?"
    parameters.append(limit)

    cursor.execute(query, parameters)
    rows = cursor.fetchall()
    connection.close()

    return [dict(row) for row in rows]


# ============================================================
# BUILD CANDIDATE CONTEXT
# ============================================================

def build_candidate_context(
    papers: list[dict],
) -> str:

    if not papers:
        return "Δεν βρέθηκαν candidate papers."

    sections = []

    for paper in papers:

        summary_text = paper.get("summary_el") or paper.get("abstract") or "Δεν υπάρχει διαθέσιμη περίληψη."

        sections.append(
            f"""
============================================================
PMID: {paper["pmid"]}

Τίτλος:
{paper["title"]}

Κατάσταση:
{paper["condition"]}

Τύπος μελέτης:
{paper["study_type"]}

Ημερομηνία:
{paper["publication_date"]}

Σημαντικότητα:
{paper["importance"]}/5

Επίπεδο τεκμηρίωσης:
{paper["evidence_level"]}

Περίληψη/Abstract:
{summary_text}
"""
        )

    return "\n".join(sections)


# ============================================================
# AI RELEVANCE RERANKING
# ============================================================

def rerank_papers(
    question: str,
    interpretation: dict,
    papers: list[dict],
) -> list[dict]:

    if not papers:
        return []

    candidate_context = build_candidate_context(papers)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": f"""
Είσαι μηχανισμός αξιολόγησης σχετικότητας επιστημονικών papers.

Ο στόχος σου είναι να αποφασίσεις ποια από τα candidate papers
είναι πραγματικά χρήσιμα για να απαντηθεί η συγκεκριμένη ερώτηση.

Δεν πρέπει να απαντήσεις στην ερώτηση.

------------------------------------------------------------
RELEVANCE SCORE
------------------------------------------------------------

Δώσε score από 0 έως 10.

10 = Άμεσα σχετικό. Απαντά ουσιαστικά στην ερώτηση.
8-9 = Πολύ σχετικό. Παρέχει σημαντική και χρήσιμη πληροφορία.
6-7 = Σχετικό αλλά όχι πλήρως.
5 = Οριακά χρήσιμο.
0-4 = Άσχετο ή πολύ έμμεσα σχετικό.

------------------------------------------------------------
QUESTION
------------------------------------------------------------

{question}

------------------------------------------------------------
QUESTION INTERPRETATION
------------------------------------------------------------

Conditions:
{", ".join(interpretation["conditions"])}

Topic:
{interpretation["topic"]}

Question type:
{interpretation["question_type"]}

Search terms:
{", ".join(interpretation["search_terms"])}

------------------------------------------------------------
CANDIDATE PAPERS
------------------------------------------------------------

{candidate_context}

------------------------------------------------------------
OUTPUT FORMAT
------------------------------------------------------------

Επέστρεψε ΜΟΝΟ μία γραμμή για κάθε paper:

PMID=<pmid>|score=<0-10>

Μην γράψεις τίποτα άλλο.
""",
            },
        ],
    )

    text = response.choices[0].message.content.strip()

    scores = {}

    for line in text.splitlines():

        line = line.strip()

        if not line.startswith("PMID="):
            continue

        try:

            parts = line.split("|")

            pmid_part = parts[0].strip()
            score_part = parts[1].strip()

            pmid = pmid_part.split("=", 1)[1].strip()

            score = int(score_part.split("=", 1)[1].strip())

            score = max(0, min(score, 10))

            scores[pmid] = score

        except (IndexError, ValueError):
            continue

    ranked_papers = []

    for paper in papers:

        pmid = str(paper["pmid"])

        score = scores.get(pmid, 0)

        paper["relevance_score"] = score

        if score >= MIN_RELEVANCE_SCORE:
            ranked_papers.append(paper)

    ranked_papers.sort(
        key=lambda paper: (
            paper["relevance_score"],
            paper["importance"],
            paper["confidence"],
            paper["publication_date"] or "",
        ),
        reverse=True,
    )

    return ranked_papers[:FINAL_PAPER_LIMIT]


# ============================================================
# BUILD RESEARCH CONTEXT
# ============================================================

def build_research_context(
    papers: list[dict],
) -> str:

    if not papers:

        return (
            "Δεν βρέθηκαν αρκετά σχετικά papers "
            "στη διαθέσιμη ερευνητική βάση."
        )

    sections = []

    for paper in papers:

        summary_body = paper.get("summary_el") or f"Abstract (English): {paper.get('abstract', '')}"

        sections.append(
            f"""
============================================================
PMID:
{paper["pmid"]}

Τίτλος:
{paper["title"]}

Κατάσταση:
{paper["condition"]}

Τύπος μελέτης:
{paper["study_type"]}

Ημερομηνία δημοσίευσης:
{paper["publication_date"]}

Σημαντικότητα:
{paper["importance"]}/5

Επίπεδο τεκμηρίωσης:
{paper["evidence_level"]}

Relevance score:
{paper.get("relevance_score", "N/A")}/10

Περιεχόμενο / Περίληψη:
{summary_body}

Βασικό εύρημα:
{paper.get("key_finding_el", "Δεν διατίθεται ξεχωριστό πεδίο.")}

Γιατί έχει σημασία:
{paper.get("why_it_matters_el", "Δεν διατίθεται ξεχωριστό πεδίο.")}

Περιορισμοί:
{paper.get("limitations_el", "Δεν διατίθεται ξεχωριστό πεδίο.")}
"""
        )

    return "\n".join(sections)


# ============================================================
# ANSWER GENERATION
# ============================================================

def answer_question(
    question: str,
    papers: list[dict],
    interpretation: dict,
) -> str:

    context = build_research_context(papers)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": f"""
Ερώτηση χρήστη:

{question}

------------------------------------------------------------

Ανάλυση ερώτησης:

Conditions:
{", ".join(interpretation["conditions"])}

Topic:
{interpretation["topic"]}

Question type:
{interpretation["question_type"]}

Search mode:
{interpretation["search_mode"]}

Search terms:
{", ".join(interpretation["search_terms"])}

------------------------------------------------------------

Παρακάτω υπάρχουν ΜΟΝΟ τα papers που πέρασαν
τον έλεγχο σχετικότητας.

{context}

------------------------------------------------------------

Οδηγίες απάντησης:

Απάντησε στην ερώτηση στα ελληνικά.
Να αναφέρεις πρώτα τα σημαντικότερα ευρήματα.
Αν αναφέρεις συγκεκριμένη μελέτη, να αναφέρεις το PMID.

Για κάθε σημαντικό εύρημα να ξεχωρίζεις:
1. Τι έδειξε η μελέτη.
2. Τι σημαίνει αυτό.
3. Τι ΔΕΝ έχει αποδειχθεί.

Μην προσθέσεις πληροφορίες που δεν υπάρχουν στα papers.
Αν δεν υπάρχουν αρκετά σχετικά papers, πες το καθαρά.
""",
            },
        ],
    )

    return response.choices[0].message.content.strip()


# ============================================================
# MAIN PROGRAM
# ============================================================

def main():

    print()
    print("Atypical Parkinsonism Research Assistant")
    print("=" * 70)
    print()

    print("Γράψε την ερώτησή σου στα ελληνικά.")
    print("Πληκτρολόγησε 'exit' για έξοδο.")
    print()

    while True:

        question = input("Ερώτηση: ").strip()

        if not question:
            continue

        if question.lower() in {"exit", "quit", "έξοδος"}:
            break

        print()
        print("Ανάλυση ερώτησης...")

        try:

            interpretation = interpret_question(question)

            relevant = interpretation["relevant"]
            conditions = interpretation["conditions"]
            topic = interpretation["topic"]
            question_type = interpretation["question_type"]
            search_mode = interpretation["search_mode"]
            search_terms = interpretation["search_terms"]

            print(f"Relevant: {relevant}")
            print(f"Conditions: {', '.join(conditions) if conditions else None}")
            print(f"Topic: {topic}")
            print(f"Question type: {question_type}")
            print(f"Search mode: {search_mode}")
            print(f"Search terms: {', '.join(search_terms) if search_terms else None}")

            if not relevant:
                print("\nΗ ερώτηση είναι εκτός του αντικειμένου της βάσης.\n")
                continue

            print("\nΑναζήτηση υποψήφιων μελετών στην ερευνητική βάση...")

            candidate_papers = get_candidate_papers(
                conditions=conditions,
                search_terms=search_terms,
                search_mode=search_mode,
                limit=CANDIDATE_LIMIT,
            )

            print(f"Βρέθηκαν {len(candidate_papers)} υποψήφιες μελέτες.")

            print("\nΑξιολόγηση σχετικότητας μελετών...")

            papers = rerank_papers(
                question=question,
                interpretation=interpretation,
                papers=candidate_papers,
            )

            print(f"Επιλέχθηκαν {len(papers)} πραγματικά σχετικές μελέτες.")

            if papers:
                print("\nSelected papers:")
                for paper in papers:
                    print(f"- PMID {paper['pmid']} (relevance {paper['relevance_score']}/10)")

            print("\nΣύνθεση απάντησης...")

            answer = answer_question(
                question=question,
                papers=papers,
                interpretation=interpretation,
            )

            print()
            print("=" * 70)
            print("ΑΠΑΝΤΗΣΗ")
            print("=" * 70)
            print()
            print(answer)
            print()

        except Exception as error:

            print("\nΣφάλμα:", error, "\n")


if __name__ == "__main__":
    main()