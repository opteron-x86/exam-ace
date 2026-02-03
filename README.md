# Project+ PK0-005 Practice Quiz

A local Python web application for studying and practicing CompTIA Project+ (PK0-005) certification exam questions. Supports multiple question types including performance-based questions (PBQs), two quiz modes, and full submission history tracking.

---

## Quick Start

```bash
# 1. Install Python dependency
pip install flask

# 2. Run the application
python app.py

# 3. Open your browser to:
#    http://localhost:5000
```

---

## Features

### Quiz Modes

| Mode | Description |
|------|-------------|
| **Study** | Immediate feedback after checking each answer. Shows correct answer and explanation. Great for learning. |
| **Exam** | Timed simulation. No feedback until you submit. Results displayed at the end with a scaled score (100-900). |

### Question Types

| Type | Description | PBQ? |
|------|-------------|------|
| **Multiple Choice** | Single correct answer from 4-5 options | No |
| **Multiple Select** | Two or more correct answers | No |
| **Matching** | Match items from two columns | Yes |
| **Ordering** | Drag items into the correct sequence | Yes |
| **Drag & Drop** | Categorize items into groups | Yes |
| **Fill In** | Type a numeric or text answer | Yes |
| **Scenario** | Multi-part question with a shared scenario | Yes |

### Quiz Configuration

- Select one or more question banks
- Filter by domain, difficulty, and question type
- Set number of questions
- Set time limit (exam mode)
- Randomize question order

### History & Analytics

- Full submission history with all past attempts
- Domain-level performance breakdown
- Score trends over time
- Pass/fail tracking (710/900 passing score)

---

## Project Structure

```
project_plus_quiz/
├── app.py                      # Flask web server (main entry point)
├── quiz_engine.py              # Question loading, quiz assembly, scoring
├── database.py                 # SQLite history database
├── config.py                   # Application configuration
├── requirements.txt            # Python dependencies
├── data/
│   └── quiz_history.db         # SQLite database (auto-created)
├── question_banks/             # ← Add your JSON question banks here
│   └── sample_bank.json        # Sample questions (all types)
├── templates/                  # HTML templates
│   ├── base.html
│   ├── index.html              # Home / quiz setup
│   ├── quiz.html               # Quiz interface
│   ├── results.html            # Results review
│   └── history.html            # Submission history
└── static/
    ├── css/style.css           # Stylesheet
    └── js/quiz.js              # Client-side quiz engine
```

---

## Creating Question Banks

Question banks are JSON files placed in the `question_banks/` directory. The app automatically detects and loads all `.json` files in that folder.

### Bank Structure

```json
{
    "bank_id": "unique_bank_id",
    "title": "Display Title",
    "description": "Optional description",
    "version": "1.0",
    "questions": [ ... ]
}
```

### Question Types Reference

#### Multiple Choice
```json
{
    "id": "mc001",
    "type": "multiple_choice",
    "domain": "1",
    "objective": "1.1",
    "tags": ["project-characteristics"],
    "difficulty": "easy",
    "question": "Which of the following best describes...?",
    "options": [
        {"key": "A", "text": "Option A text"},
        {"key": "B", "text": "Option B text"},
        {"key": "C", "text": "Option C text"},
        {"key": "D", "text": "Option D text"}
    ],
    "correct": "B",
    "explanation": "Explanation of why B is correct..."
}
```

#### Multiple Select
```json
{
    "id": "ms001",
    "type": "multiple_select",
    "domain": "1",
    "objective": "1.2",
    "difficulty": "medium",
    "question": "Select TWO that apply...",
    "select_count": 2,
    "options": [
        {"key": "A", "text": "Option A"},
        {"key": "B", "text": "Option B"},
        {"key": "C", "text": "Option C"},
        {"key": "D", "text": "Option D"},
        {"key": "E", "text": "Option E"}
    ],
    "correct": ["B", "D"],
    "explanation": "B and D are correct because..."
}
```

#### Matching (PBQ)
```json
{
    "id": "match001",
    "type": "matching",
    "domain": "1",
    "objective": "1.4",
    "difficulty": "hard",
    "question": "Match each term with its definition.",
    "pairs": [
        {"left": "Term 1", "right": "Definition 1"},
        {"left": "Term 2", "right": "Definition 2"},
        {"left": "Term 3", "right": "Definition 3"}
    ],
    "explanation": "Explanation..."
}
```

#### Ordering (PBQ)
```json
{
    "id": "order001",
    "type": "ordering",
    "domain": "2",
    "objective": "2.1",
    "difficulty": "easy",
    "question": "Place these items in the correct order.",
    "items": ["Item C", "Item A", "Item D", "Item B"],
    "correct_order": ["Item A", "Item B", "Item C", "Item D"],
    "explanation": "The correct order is A, B, C, D because..."
}
```
> Note: The `items` array is the display/shuffled order. The `correct_order` is the answer key.

#### Drag & Drop / Categorization (PBQ)
```json
{
    "id": "dd001",
    "type": "drag_drop",
    "domain": "1",
    "objective": "1.2",
    "difficulty": "medium",
    "question": "Categorize each item.",
    "categories": ["Category A", "Category B", "Category C"],
    "items": [
        {"text": "Item 1", "correct_category": "Category A"},
        {"text": "Item 2", "correct_category": "Category B"},
        {"text": "Item 3", "correct_category": "Category A"},
        {"text": "Item 4", "correct_category": "Category C"}
    ],
    "explanation": "Explanation..."
}
```

#### Fill In the Blank (PBQ)
```json
{
    "id": "fi001",
    "type": "fill_in",
    "domain": "2",
    "objective": "2.4",
    "difficulty": "hard",
    "question": "Calculate the CPI given EV=$500 and AC=$600. Round to two decimal places.",
    "correct_answers": ["0.83", "0.833", ".83"],
    "case_sensitive": false,
    "explanation": "CPI = EV / AC = $500 / $600 = 0.833"
}
```
> Tip: Include multiple accepted formats in `correct_answers` (with/without `$`, commas, different decimal places).

#### Scenario / Multi-Part (PBQ)
```json
{
    "id": "sc001",
    "type": "scenario",
    "domain": "2",
    "objective": "2.4",
    "difficulty": "hard",
    "scenario": "Long scenario text describing the situation...",
    "parts": [
        {
            "id": "sc001a",
            "type": "fill_in",
            "question": "Calculate the SV.",
            "correct_answers": ["-10000", "-$10,000"],
            "explanation": "SV = EV - PV = ..."
        },
        {
            "id": "sc001b",
            "type": "multiple_choice",
            "question": "Based on the data, the project is:",
            "options": [
                {"key": "A", "text": "Ahead of schedule"},
                {"key": "B", "text": "Behind schedule"},
                {"key": "C", "text": "On schedule"}
            ],
            "correct": "B",
            "explanation": "SV is negative, meaning behind schedule."
        }
    ],
    "explanation": "Overall explanation for the scenario..."
}
```
> Scenario parts support `multiple_choice`, `multiple_select`, and `fill_in` types.

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (must be unique across all banks) |
| `type` | Yes | Question type (see types above) |
| `domain` | Yes | Exam domain: "1", "2", "3", or "4" |
| `objective` | Recommended | Specific objective (e.g., "1.1", "2.3") |
| `difficulty` | Recommended | "easy", "medium", or "hard" |
| `tags` | Optional | Array of topic tags for filtering |
| `question` | Yes | The question text |
| `explanation` | Recommended | Explanation shown after answering |

### Domain Reference

| Domain | Name | Weight |
|--------|------|--------|
| 1 | Project Management Concepts | 33% |
| 2 | Project Life Cycle Phases | 30% |
| 3 | Tools and Documentation | 19% |
| 4 | Basics of IT and Governance | 18% |

---

## Scoring

- **Percentage**: Raw correct / total questions × 100
- **Scaled Score**: Mapped to CompTIA's 100-900 scale
- **Passing Score**: 710 / 900
- **PBQ Partial Credit**: Matching, ordering, and drag-drop questions award partial credit for partially correct answers

---

## Keyboard Shortcuts (Quiz Page)

| Key | Action |
|-----|--------|
| → or `n` | Next question |
| ← or `p` | Previous question |
| `f` | Toggle flag on current question |

---

## Tips

1. **Start with Study Mode** to learn the material and understand explanations.
2. **Use Exam Mode** to simulate real test conditions when you feel ready.
3. **Review domain breakdowns** after each attempt to identify weak areas.
4. **Create topic-specific banks** (e.g., `evm_questions.json`, `agile_questions.json`) for targeted practice.
5. **Use the difficulty filter** to progressively challenge yourself.
