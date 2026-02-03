"""SQLite database management for quiz submission history."""
import sqlite3
import json
import os
from datetime import datetime, timezone
from config import DATABASE_PATH


def get_connection():
    """Get a database connection with row_factory."""
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id TEXT PRIMARY KEY,
            mode TEXT NOT NULL CHECK(mode IN ('study', 'exam')),
            bank_ids TEXT NOT NULL,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            time_spent_seconds INTEGER DEFAULT 0,
            total_questions INTEGER NOT NULL,
            correct_count INTEGER DEFAULT 0,
            score_percentage REAL DEFAULT 0,
            scaled_score INTEGER DEFAULT 0,
            passed INTEGER DEFAULT 0,
            config_json TEXT
        );

        CREATE TABLE IF NOT EXISTS question_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            question_id TEXT NOT NULL,
            question_type TEXT NOT NULL,
            domain TEXT,
            objective TEXT,
            user_answer TEXT,
            correct_answer TEXT,
            is_correct INTEGER NOT NULL DEFAULT 0,
            partial_score REAL DEFAULT 0,
            time_spent_seconds INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES quiz_sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS flagged_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id TEXT NOT NULL,
            bank_id TEXT NOT NULL,
            reason TEXT DEFAULT 'review',
            created_at TEXT NOT NULL,
            UNIQUE(question_id, bank_id)
        );

        CREATE INDEX IF NOT EXISTS idx_responses_session
            ON question_responses(session_id);
        CREATE INDEX IF NOT EXISTS idx_responses_domain
            ON question_responses(domain);
        CREATE INDEX IF NOT EXISTS idx_sessions_mode
            ON quiz_sessions(mode);
    """)
    conn.commit()
    conn.close()


# ── Session operations ─────────────────────────────────────────────

def create_session(session_id, mode, bank_ids, total_questions, config=None):
    """Create a new quiz session."""
    conn = get_connection()
    conn.execute(
        """INSERT INTO quiz_sessions
           (id, mode, bank_ids, started_at, total_questions, config_json)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            session_id,
            mode,
            json.dumps(bank_ids),
            datetime.now(timezone.utc).isoformat(),
            total_questions,
            json.dumps(config) if config else None,
        ),
    )
    conn.commit()
    conn.close()


def complete_session(session_id, results):
    """Mark a session as complete with scored results."""
    conn = get_connection()
    conn.execute(
        """UPDATE quiz_sessions
           SET completed_at = ?,
               time_spent_seconds = ?,
               correct_count = ?,
               score_percentage = ?,
               scaled_score = ?,
               passed = ?
           WHERE id = ?""",
        (
            datetime.now(timezone.utc).isoformat(),
            results["time_spent_seconds"],
            results["correct_count"],
            results["score_percentage"],
            results["scaled_score"],
            1 if results["passed"] else 0,
            session_id,
        ),
    )
    conn.commit()
    conn.close()


def save_responses(session_id, responses):
    """Save individual question responses."""
    conn = get_connection()
    conn.executemany(
        """INSERT INTO question_responses
           (session_id, question_id, question_type, domain, objective,
            user_answer, correct_answer, is_correct, partial_score,
            time_spent_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                session_id,
                r["question_id"],
                r["question_type"],
                r.get("domain"),
                r.get("objective"),
                json.dumps(r.get("user_answer")),
                json.dumps(r.get("correct_answer")),
                1 if r.get("is_correct") else 0,
                r.get("partial_score", 0),
                r.get("time_spent_seconds", 0),
            )
            for r in responses
        ],
    )
    conn.commit()
    conn.close()


def get_session(session_id):
    """Get a session by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM quiz_sessions WHERE id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def get_session_responses(session_id):
    """Get all responses for a session."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM question_responses WHERE session_id = ? ORDER BY id",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_sessions(limit=50, offset=0, mode=None):
    """Get all sessions, optionally filtered by mode."""
    conn = get_connection()
    query = "SELECT * FROM quiz_sessions"
    params = []
    if mode:
        query += " WHERE mode = ?"
        params.append(mode)
    query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id):
    """Delete a session and its responses."""
    conn = get_connection()
    conn.execute("DELETE FROM quiz_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()


# ── Statistics ─────────────────────────────────────────────────────

def get_overall_stats():
    """Compute aggregate statistics across all sessions."""
    conn = get_connection()

    session_stats = conn.execute("""
        SELECT
            COUNT(*) as total_attempts,
            SUM(CASE WHEN mode = 'exam' THEN 1 ELSE 0 END) as exam_attempts,
            SUM(CASE WHEN mode = 'study' THEN 1 ELSE 0 END) as study_attempts,
            AVG(score_percentage) as avg_score,
            MAX(score_percentage) as best_score,
            SUM(CASE WHEN passed = 1 THEN 1 ELSE 0 END) as pass_count,
            SUM(total_questions) as total_questions_answered
        FROM quiz_sessions
        WHERE completed_at IS NOT NULL
    """).fetchone()

    domain_stats = conn.execute("""
        SELECT
            domain,
            COUNT(*) as total,
            SUM(is_correct) as correct,
            ROUND(AVG(is_correct) * 100, 1) as pct
        FROM question_responses
        WHERE domain IS NOT NULL
        GROUP BY domain
        ORDER BY domain
    """).fetchall()

    recent = conn.execute("""
        SELECT scaled_score, started_at, mode
        FROM quiz_sessions
        WHERE completed_at IS NOT NULL
        ORDER BY started_at DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return {
        "sessions": dict(session_stats) if session_stats else {},
        "domains": [dict(d) for d in domain_stats],
        "recent_scores": [dict(r) for r in recent],
    }


def get_domain_breakdown(session_id):
    """Get domain-level performance for a specific session."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT
               domain,
               COUNT(*) as total,
               SUM(is_correct) as correct,
               ROUND(AVG(is_correct) * 100, 1) as pct
           FROM question_responses
           WHERE session_id = ? AND domain IS NOT NULL
           GROUP BY domain
           ORDER BY domain""",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Flagged questions ──────────────────────────────────────────────

def flag_question(question_id, bank_id, reason="review"):
    """Flag a question for later review."""
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO flagged_questions
           (question_id, bank_id, reason, created_at)
           VALUES (?, ?, ?, ?)""",
        (question_id, bank_id, reason, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def unflag_question(question_id, bank_id):
    """Remove flag from a question."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM flagged_questions WHERE question_id = ? AND bank_id = ?",
        (question_id, bank_id),
    )
    conn.commit()
    conn.close()


def get_flagged_questions():
    """Get all flagged question IDs."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM flagged_questions").fetchall()
    conn.close()
    return [dict(r) for r in rows]
