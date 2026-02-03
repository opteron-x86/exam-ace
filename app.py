"""Project+ PK0-005 Quiz Application – Flask backend."""
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
import database as db
import quiz_engine as engine
from config import DOMAIN_WEIGHTS, QUESTION_TYPES, PASSING_SCORE

app = Flask(__name__)
app.secret_key = "projectplus-local-quiz-key"

# Initialize the database on startup
db.init_db()


# ── Page routes ────────────────────────────────────────────────────

@app.route("/")
def index():
    """Home page – quiz setup."""
    banks = engine.list_banks()
    stats = db.get_overall_stats()
    return render_template(
        "index.html",
        banks=banks,
        stats=stats,
        domain_weights=DOMAIN_WEIGHTS,
        question_types=QUESTION_TYPES,
    )


@app.route("/quiz/<session_id>")
def quiz_page(session_id):
    """Quiz interface page."""
    session = db.get_session(session_id)
    if not session:
        return redirect(url_for("index"))
    return render_template("quiz.html", session_id=session_id)


@app.route("/results/<session_id>")
def results_page(session_id):
    """Results review page."""
    session = db.get_session(session_id)
    if not session:
        return redirect(url_for("index"))
    responses = db.get_session_responses(session_id)
    domains = db.get_domain_breakdown(session_id)
    return render_template(
        "results.html",
        session=session,
        responses=responses,
        domains=domains,
        domain_weights=DOMAIN_WEIGHTS,
        passing_score=PASSING_SCORE,
    )


@app.route("/history")
def history_page():
    """Submission history page."""
    sessions = db.get_all_sessions(limit=100)
    stats = db.get_overall_stats()
    return render_template(
        "history.html",
        sessions=sessions,
        stats=stats,
        domain_weights=DOMAIN_WEIGHTS,
    )


# ── API routes ─────────────────────────────────────────────────────

@app.route("/api/banks")
def api_banks():
    """List available question banks."""
    return jsonify(engine.list_banks())


@app.route("/api/quiz/start", methods=["POST"])
def api_start_quiz():
    """
    Start a new quiz session.

    Expects JSON body:
      bank_files: list of bank filenames
      mode: 'study' or 'exam'
      count: number of questions (optional)
      domains: list of domain strings (optional)
      difficulties: list of difficulty strings (optional)
      question_types: list of type strings (optional)
      time_limit: minutes (optional, exam mode)
      randomize: bool (optional, default true)
    """
    data = request.get_json()
    bank_files = data.get("bank_files", [])
    mode = data.get("mode", "study")
    count = data.get("count")
    domains = data.get("domains")
    difficulties = data.get("difficulties")
    question_types = data.get("question_types")
    time_limit = data.get("time_limit", 0)
    randomize = data.get("randomize", True)

    if not bank_files:
        return jsonify({"error": "No question banks selected"}), 400

    session_id, questions = engine.build_quiz(
        bank_files,
        count=count,
        domains=domains,
        difficulties=difficulties,
        question_types=question_types,
        randomize=randomize,
    )

    if not questions:
        return jsonify({"error": "No questions match the selected criteria"}), 400

    # Store session
    config = {
        "time_limit": time_limit,
        "domains": domains,
        "difficulties": difficulties,
        "question_types": question_types,
        "randomize": randomize,
    }
    db.create_session(session_id, mode, bank_files, len(questions), config)

    # Prepare questions for client
    # In study mode we include correct answers; in exam mode we strip them
    client_questions = []
    for q in questions:
        cq = _prepare_question_for_client(q, include_answers=(mode == "study"))
        client_questions.append(cq)

    return jsonify({
        "session_id": session_id,
        "mode": mode,
        "time_limit": time_limit,
        "total_questions": len(questions),
        "questions": client_questions,
        # Store full questions server-side keyed by session for scoring
        "_scoring_key": session_id,
    })


@app.route("/api/quiz/<session_id>/submit", methods=["POST"])
def api_submit_quiz(session_id):
    """
    Submit quiz answers for scoring.

    Expects JSON body:
      answers: dict mapping question_id -> user_answer
      time_spent_seconds: int
    """
    data = request.get_json()
    answers = data.get("answers", {})
    time_spent = data.get("time_spent_seconds", 0)

    # Load the session to get bank files
    session = db.get_session(session_id)
    if not session:
        return jsonify({"error": "Session not found"}), 404

    # Reload the questions (we need correct answers for scoring)
    config = json.loads(session.get("config_json") or "{}")
    bank_ids = json.loads(session["bank_ids"])
    all_questions = engine.load_questions(bank_ids)

    # Filter to just the questions in this session by matching IDs
    answered_ids = set(answers.keys())
    # We need to find the original questions - reload with same settings
    # For simplicity, just match by ID from all loaded questions
    question_map = {q["id"]: q for q in all_questions}

    # Build ordered question list from answer keys
    quiz_questions = [question_map[qid] for qid in answers if qid in question_map]

    # Also include unanswered questions (scored as incorrect)
    # The client should send all question IDs even if unanswered

    results = engine.score_quiz(quiz_questions, answers, time_spent)

    # Persist results
    db.complete_session(session_id, results)
    db.save_responses(session_id, results["responses"])

    return jsonify({
        "session_id": session_id,
        "results": results,
    })


@app.route("/api/quiz/<session_id>/check", methods=["POST"])
def api_check_answer(session_id):
    """
    Check a single answer (study mode).

    Expects JSON:
      question: full question object
      answer: user's answer
    """
    data = request.get_json()
    question = data.get("question", {})
    user_answer = data.get("answer")
    result = engine.score_question(question, user_answer)
    return jsonify(result)


@app.route("/api/history")
def api_history():
    """Get session history as JSON."""
    mode = request.args.get("mode")
    sessions = db.get_all_sessions(limit=100, mode=mode)
    return jsonify(sessions)


@app.route("/api/history/<session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    """Delete a session."""
    db.delete_session(session_id)
    return jsonify({"deleted": True})


@app.route("/api/stats")
def api_stats():
    """Get overall statistics."""
    return jsonify(db.get_overall_stats())


@app.route("/api/results/<session_id>")
def api_results(session_id):
    """Get full results for a session."""
    session = db.get_session(session_id)
    if not session:
        return jsonify({"error": "Not found"}), 404
    responses = db.get_session_responses(session_id)
    domains = db.get_domain_breakdown(session_id)
    return jsonify({
        "session": session,
        "responses": responses,
        "domains": domains,
    })


# ── Helpers ────────────────────────────────────────────────────────

def _prepare_question_for_client(question, include_answers=False):
    """Prepare a question dict for sending to the client."""
    q = dict(question)

    # Always include these
    keep = ["id", "type", "domain", "objective", "difficulty",
            "question", "options", "tags", "select_count",
            "pairs", "items", "categories", "scenario", "parts",
            "_bank_id"]

    result = {k: q[k] for k in keep if k in q}

    if include_answers:
        # Study mode – include answers and explanations
        for key in ["correct", "correct_answers", "correct_order",
                    "explanation", "case_sensitive"]:
            if key in q:
                result[key] = q[key]
        # For matching, correct is embedded in pairs
        # For drag_drop, correct is in items
        # For scenarios, correct is in parts

    # For matching in study mode, shuffle right column
    if q.get("type") == "matching" and "pairs" in result:
        import random as _r
        shuffled_rights = [p["right"] for p in result["pairs"]]
        _r.shuffle(shuffled_rights)
        result["shuffled_rights"] = shuffled_rights

    # For ordering, shuffle the items
    if q.get("type") == "ordering" and "items" in q:
        import random as _r
        items_copy = list(q["items"])
        _r.shuffle(items_copy)
        result["items"] = items_copy

    return result


# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  Project+ PK0-005 Practice Quiz")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 60 + "\n")
    app.run(debug=True, port=5000)
