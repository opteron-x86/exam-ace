"""Quiz engine: loads question banks, assembles quizzes, and scores answers."""
import json
import os
import random
import uuid
from config import (
    QUESTION_BANKS_DIR,
    DOMAIN_WEIGHTS,
    PASSING_SCORE,
    SCORE_SCALE_MAX,
    SCORE_SCALE_MIN,
)


# ── Question bank loading ──────────────────────────────────────────

def list_banks():
    """Return metadata for all available question banks."""
    banks = []
    if not os.path.isdir(QUESTION_BANKS_DIR):
        os.makedirs(QUESTION_BANKS_DIR, exist_ok=True)
        return banks

    for fname in sorted(os.listdir(QUESTION_BANKS_DIR)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(QUESTION_BANKS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            questions = data.get("questions", [])
            # Count by type
            type_counts = {}
            domain_counts = {}
            for q in questions:
                qtype = q.get("type", "unknown")
                type_counts[qtype] = type_counts.get(qtype, 0) + 1
                dom = q.get("domain", "?")
                domain_counts[dom] = domain_counts.get(dom, 0) + 1
            banks.append({
                "file": fname,
                "bank_id": data.get("bank_id", fname),
                "title": data.get("title", fname),
                "description": data.get("description", ""),
                "version": data.get("version", "1.0"),
                "question_count": len(questions),
                "type_counts": type_counts,
                "domain_counts": domain_counts,
            })
        except (json.JSONDecodeError, IOError):
            continue
    return banks


def load_bank(filename):
    """Load a full question bank from a JSON file."""
    path = os.path.join(QUESTION_BANKS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_questions(bank_filenames):
    """Load and merge questions from one or more bank files."""
    questions = []
    for fname in bank_filenames:
        bank = load_bank(fname)
        bank_id = bank.get("bank_id", fname)
        for q in bank.get("questions", []):
            q["_bank_id"] = bank_id
            q["_bank_file"] = fname
            # Flatten scenario parts for counting purposes
            questions.append(q)
    return questions


# ── Quiz assembly ──────────────────────────────────────────────────

def build_quiz(bank_filenames, count=None, domains=None, difficulties=None,
               question_types=None, randomize=True):
    """
    Assemble a quiz from the specified banks with optional filters.

    Returns (session_id, question_list).
    """
    all_questions = load_questions(bank_filenames)

    # Apply filters
    filtered = all_questions
    if domains:
        filtered = [q for q in filtered if q.get("domain") in domains]
    if difficulties:
        filtered = [q for q in filtered if q.get("difficulty") in difficulties]
    if question_types:
        filtered = [q for q in filtered if q.get("type") in question_types]

    if randomize:
        random.shuffle(filtered)

    # Trim to requested count
    if count and count < len(filtered):
        filtered = filtered[:count]

    session_id = str(uuid.uuid4())[:8]
    return session_id, filtered


# ── Scoring ────────────────────────────────────────────────────────

def score_question(question, user_answer):
    """
    Score a single question.

    Returns dict with:
      is_correct (bool), partial_score (float 0-1),
      correct_answer, feedback (str)
    """
    qtype = question.get("type")

    if qtype == "multiple_choice":
        return _score_mc(question, user_answer)
    elif qtype == "multiple_select":
        return _score_ms(question, user_answer)
    elif qtype == "matching":
        return _score_matching(question, user_answer)
    elif qtype == "ordering":
        return _score_ordering(question, user_answer)
    elif qtype == "drag_drop":
        return _score_drag_drop(question, user_answer)
    elif qtype == "fill_in":
        return _score_fill_in(question, user_answer)
    elif qtype == "scenario":
        return _score_scenario(question, user_answer)
    else:
        return {
            "is_correct": False,
            "partial_score": 0,
            "correct_answer": None,
            "feedback": f"Unknown question type: {qtype}",
        }


def _score_mc(question, user_answer):
    correct = question["correct"]
    is_correct = user_answer == correct
    return {
        "is_correct": is_correct,
        "partial_score": 1.0 if is_correct else 0.0,
        "correct_answer": correct,
        "feedback": question.get("explanation", ""),
    }


def _score_ms(question, user_answer):
    correct_set = set(question["correct"])
    user_set = set(user_answer) if isinstance(user_answer, list) else set()

    if user_set == correct_set:
        score = 1.0
        is_correct = True
    else:
        # Partial credit: correct selections / total needed, minus wrong picks
        right_picks = len(user_set & correct_set)
        wrong_picks = len(user_set - correct_set)
        score = max(0, (right_picks - wrong_picks)) / len(correct_set)
        is_correct = False

    return {
        "is_correct": is_correct,
        "partial_score": score,
        "correct_answer": list(correct_set),
        "feedback": question.get("explanation", ""),
    }


def _score_matching(question, user_answer):
    """user_answer: dict mapping left items to chosen right items."""
    pairs = question["pairs"]
    correct_map = {p["left"]: p["right"] for p in pairs}
    user_map = user_answer if isinstance(user_answer, dict) else {}

    correct_count = sum(
        1 for left, right in user_map.items()
        if correct_map.get(left) == right
    )
    total = len(pairs)
    score = correct_count / total if total else 0
    is_correct = correct_count == total

    return {
        "is_correct": is_correct,
        "partial_score": score,
        "correct_answer": correct_map,
        "feedback": question.get("explanation", ""),
    }


def _score_ordering(question, user_answer):
    """user_answer: list of items in user's order."""
    correct_order = question["correct_order"]
    user_order = user_answer if isinstance(user_answer, list) else []

    if user_order == correct_order:
        return {
            "is_correct": True,
            "partial_score": 1.0,
            "correct_answer": correct_order,
            "feedback": question.get("explanation", ""),
        }

    # Partial credit based on items in correct position
    correct_positions = sum(
        1 for i, item in enumerate(user_order)
        if i < len(correct_order) and item == correct_order[i]
    )
    total = len(correct_order)
    score = correct_positions / total if total else 0

    return {
        "is_correct": False,
        "partial_score": score,
        "correct_answer": correct_order,
        "feedback": question.get("explanation", ""),
    }


def _score_drag_drop(question, user_answer):
    """user_answer: dict mapping item text to chosen category."""
    items = question["items"]
    correct_map = {item["text"]: item["correct_category"] for item in items}
    user_map = user_answer if isinstance(user_answer, dict) else {}

    correct_count = sum(
        1 for text, cat in user_map.items()
        if correct_map.get(text) == cat
    )
    total = len(items)
    score = correct_count / total if total else 0
    is_correct = correct_count == total

    return {
        "is_correct": is_correct,
        "partial_score": score,
        "correct_answer": correct_map,
        "feedback": question.get("explanation", ""),
    }


def _score_fill_in(question, user_answer):
    """user_answer: string input from user."""
    correct_answers = question.get("correct_answers", [])
    case_sensitive = question.get("case_sensitive", False)

    user_str = str(user_answer).strip() if user_answer else ""
    if not case_sensitive:
        user_str = user_str.lower()
        correct_answers = [a.lower() for a in correct_answers]

    # Strip common prefixes like $ for financial answers
    user_clean = user_str.replace("$", "").replace(",", "").strip()
    correct_clean = [a.replace("$", "").replace(",", "").strip()
                     for a in correct_answers]

    is_correct = user_str in correct_answers or user_clean in correct_clean

    return {
        "is_correct": is_correct,
        "partial_score": 1.0 if is_correct else 0.0,
        "correct_answer": question.get("correct_answers", []),
        "feedback": question.get("explanation", ""),
    }


def _score_scenario(question, user_answer):
    """user_answer: dict mapping part id to part answer."""
    parts = question.get("parts", [])
    user_parts = user_answer if isinstance(user_answer, dict) else {}

    part_results = []
    total_score = 0
    all_correct = True

    for part in parts:
        part_id = part["id"]
        part_answer = user_parts.get(part_id)
        # Build a mini-question from the part
        mini_q = {**part}
        if "explanation" not in mini_q:
            mini_q["explanation"] = ""
        result = score_question(mini_q, part_answer)
        result["part_id"] = part_id
        part_results.append(result)
        total_score += result["partial_score"]
        if not result["is_correct"]:
            all_correct = False

    avg_score = total_score / len(parts) if parts else 0

    return {
        "is_correct": all_correct,
        "partial_score": avg_score,
        "correct_answer": {p["id"]: p.get("correct", p.get("correct_answers", p.get("correct_order")))
                           for p in parts},
        "feedback": question.get("explanation", ""),
        "part_results": part_results,
    }


# ── Full quiz scoring ──────────────────────────────────────────────

def score_quiz(questions, answers, time_spent_seconds=0):
    """
    Score an entire quiz.

    Args:
        questions: list of question dicts
        answers: dict mapping question_id to user_answer
        time_spent_seconds: total time spent

    Returns:
        dict with overall results and per-question detail.
    """
    responses = []
    total_points = 0
    earned_points = 0

    for q in questions:
        qid = q["id"]
        user_answer = answers.get(qid)
        result = score_question(q, user_answer)

        # Each question is worth 1 point (PBQs may have partial credit)
        weight = 1
        total_points += weight
        earned_points += result["partial_score"] * weight

        responses.append({
            "question_id": qid,
            "question_type": q.get("type"),
            "domain": q.get("domain"),
            "objective": q.get("objective"),
            "user_answer": user_answer,
            "correct_answer": result["correct_answer"],
            "is_correct": result["is_correct"],
            "partial_score": result["partial_score"],
            "feedback": result["feedback"],
            "part_results": result.get("part_results"),
            "time_spent_seconds": 0,
        })

    # Calculate percentage and scaled score
    pct = (earned_points / total_points * 100) if total_points else 0
    # Map percentage to 100-900 scale
    scaled = int(SCORE_SCALE_MIN + (pct / 100) * (SCORE_SCALE_MAX - SCORE_SCALE_MIN))
    scaled = max(SCORE_SCALE_MIN, min(SCORE_SCALE_MAX, scaled))
    passed = scaled >= PASSING_SCORE

    # Domain breakdown
    domain_results = {}
    for r in responses:
        dom = r.get("domain", "?")
        if dom not in domain_results:
            domain_results[dom] = {"total": 0, "correct": 0, "earned": 0}
        domain_results[dom]["total"] += 1
        domain_results[dom]["earned"] += r["partial_score"]
        if r["is_correct"]:
            domain_results[dom]["correct"] += 1

    for dom, data in domain_results.items():
        data["percentage"] = round(data["earned"] / data["total"] * 100, 1) if data["total"] else 0
        info = DOMAIN_WEIGHTS.get(dom, {})
        data["name"] = info.get("name", f"Domain {dom}")
        data["weight"] = info.get("weight", 0)

    correct_count = sum(1 for r in responses if r["is_correct"])

    return {
        "total_questions": len(questions),
        "correct_count": correct_count,
        "earned_points": round(earned_points, 2),
        "total_points": total_points,
        "score_percentage": round(pct, 1),
        "scaled_score": scaled,
        "passed": passed,
        "passing_score": PASSING_SCORE,
        "time_spent_seconds": time_spent_seconds,
        "domain_results": domain_results,
        "responses": responses,
    }
