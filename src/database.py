import sqlite3
from pathlib import Path
from typing import Optional

# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATABASE_PATH = DATA_DIR / "research.db"


# ============================================================
# CONNECTION
# ============================================================

def get_connection() -> sqlite3.Connection:
    """Open a connection to the research database."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


# ============================================================
# SAVE SCREENING RESULT
# ============================================================

def save_screening_result(
    pmid: str,
    relevant: bool,
    relevance_type: str,
    condition: str,
    study_type: str,
    importance: int,
    evidence_level: str,
    confidence: int,
    reason: str,
) -> None:
    from datetime import datetime

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE papers
        SET
            screening_status = ?,
            relevant = ?,
            relevance_type = ?,
            condition = ?,
            study_type = ?,
            importance = ?,
            evidence_level = ?,
            confidence = ?,
            screening_reason = ?,
            screened_at = ?
        WHERE pmid = ?
        """,
        (
            "completed",
            int(relevant),
            relevance_type,
            condition,
            study_type,
            importance,
            evidence_level,
            confidence,
            reason,
            datetime.now().isoformat(timespec="seconds"),
            pmid,
        ),
    )

    connection.commit()
    connection.close()


# Alias για συμβατότητα
save_screening = save_screening_result


# ============================================================
# SAVE SUMMARY
# ============================================================

def save_summary(
    pmid: str,
    title_el: str,
    summary_el: str,
    key_finding_el: str,
    why_it_matters_el: str,
    limitations_el: str,
) -> None:
    """Αποθηκεύει τον ελληνικό τίτλο και την ελληνική περίληψη στη βάση."""
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
            title_el,
            summary_el,
            key_finding_el,
            why_it_matters_el,
            limitations_el,
            "completed",
            pmid,
        ),
    )

    connection.commit()
    connection.close()


# ============================================================
# CLINICAL TRIALS FUNCTIONS
# ============================================================

def save_clinical_trial(trial_data: dict) -> bool:
    """Αποθηκεύει μια κλινική δοκιμή από το ClinicalTrials.gov στη βάση."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinical_trials (
            nct_id TEXT PRIMARY KEY,
            title TEXT,
            title_el TEXT,
            condition TEXT,
            status TEXT,
            phase TEXT,
            interventions TEXT,
            summary TEXT,
            summary_el TEXT,
            relevant INTEGER,
            importance INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("SELECT nct_id FROM clinical_trials WHERE nct_id = ?", (trial_data["nct_id"],))
    if cursor.fetchone():
        connection.close()
        return False

    cursor.execute("""
        INSERT INTO clinical_trials (nct_id, title, condition, status, phase, interventions, summary, relevant)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (
        trial_data["nct_id"],
        trial_data["title"],
        trial_data["condition"],
        trial_data["status"],
        trial_data["phase"],
        trial_data["interventions"],
        trial_data["summary"]
    ))

    connection.commit()
    connection.close()
    return True


def save_trial_screening(nct_id: str, relevant: bool, importance: int) -> None:
    """Ενημερώνει το αποτέλεσμα του screening για μια κλινική δοκιμή."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE clinical_trials
        SET relevant = ?, importance = ?
        WHERE nct_id = ?
    """, (1 if relevant else -1, importance, nct_id))

    connection.commit()
    connection.close()


# ============================================================
# INITIALIZE & MIGRATE DATABASE
# ============================================================

def initialize_database() -> None:
    """Create all database tables if they don't already exist."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            pmid TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            abstract TEXT,
            journal TEXT,
            publication_date TEXT,
            doi TEXT,
            pubmed_url TEXT,
            first_seen TEXT NOT NULL,
            last_updated TEXT NOT NULL,
            screening_status TEXT,
            relevant INTEGER,
            condition TEXT,
            study_type TEXT,
            importance INTEGER,
            evidence_level TEXT,
            confidence INTEGER,
            screening_reason TEXT,
            screened_at TEXT,
            relevance_type TEXT,
            summary_el TEXT,
            key_finding_el TEXT,
            why_it_matters_el TEXT,
            limitations_el TEXT,
            summary_status TEXT,
            sent_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS paper_topics (
            pmid TEXT NOT NULL,
            topic TEXT NOT NULL,
            PRIMARY KEY (pmid, topic),
            FOREIGN KEY (pmid) REFERENCES papers(pmid)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    connection.commit()
    connection.close()


def migrate_database() -> None:
    """Add new columns to existing databases if necessary."""
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(papers)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    new_columns = {
        "screening_status": "TEXT",
        "relevant": "INTEGER",
        "condition": "TEXT",
        "study_type": "TEXT",
        "importance": "INTEGER",
        "evidence_level": "TEXT",
        "confidence": "INTEGER",
        "screening_reason": "TEXT",
        "screened_at": "TEXT",
        "relevance_type": "TEXT",
        "summary_el": "TEXT",
        "key_finding_el": "TEXT",
        "why_it_matters_el": "TEXT",
        "limitations_el": "TEXT",
        "summary_status": "TEXT",
    }

    for column, column_type in new_columns.items():
        if column not in existing_columns:
            cursor.execute(f"ALTER TABLE papers ADD COLUMN {column} {column_type}")
            print(f"Added database column: {column}")

    connection.commit()
    connection.close()


# ============================================================
# AGENT STATE & HELPERS
# ============================================================

def get_state(key: str) -> Optional[str]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT value FROM agent_state WHERE key = ?", (key,))
    row = cursor.fetchone()
    connection.close()
    return row["value"] if row else None


def set_state(key: str, value: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        INSERT INTO agent_state (key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, value))
    connection.commit()
    connection.close()


def get_paper_count() -> int:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) AS count FROM papers")
    row = cursor.fetchone()
    connection.close()
    return row["count"]


def get_all_papers() -> list[dict]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT * FROM papers ORDER BY publication_date DESC")
    rows = cursor.fetchall()
    connection.close()
    return [dict(row) for row in rows]


def get_pending_papers(limit: int = 5) -> list[dict]:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("""
        SELECT pmid, title, abstract, journal, publication_date, doi, pubmed_url
        FROM papers
        WHERE screening_status IS NULL OR screening_status = 'pending'
        ORDER BY publication_date DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    connection.close()
    return [dict(row) for row in rows]


def mark_processing(pmid: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE papers SET screening_status = 'processing' WHERE pmid = ?", (pmid,))
    connection.commit()
    connection.close()


def mark_error(pmid: str, error_message: str) -> None:
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE papers SET screening_status = 'error', screening_reason = ? WHERE pmid = ?", (error_message, pmid))
    connection.commit()
    connection.close()


def mark_paper_as_sent(pmid: str) -> None:
    from datetime import datetime
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("PRAGMA table_info(papers)")
    columns = {row["name"] for row in cursor.fetchall()}
    if "sent_at" not in columns:
        cursor.execute("ALTER TABLE papers ADD COLUMN sent_at TEXT")

    cursor.execute("UPDATE papers SET sent_at = ? WHERE pmid = ?", (datetime.now().isoformat(timespec="seconds"), pmid))
    connection.commit()
    connection.close()


if __name__ == "__main__":
    print("Initializing research database...")
    initialize_database()
    migrate_database()
    print("Database created at:", DATABASE_PATH)