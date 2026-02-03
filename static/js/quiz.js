/**
 * Project+ PK0-005 Quiz Engine (Client-side)
 *
 * Handles rendering of all question types, navigation, timer,
 * answer tracking, and submission.
 */

class QuizApp {
    constructor(data) {
        this.sessionId = data.session_id;
        this.mode = data.mode;               // 'study' or 'exam'
        this.timeLimit = data.time_limit;     // minutes; 0 = unlimited
        this.questions = data.questions;
        this.totalQuestions = data.total_questions;

        this.currentIndex = 0;
        this.answers = {};                    // questionId -> answer value
        this.flagged = new Set();
        this.checked = {};                    // questionId -> {correct, feedback} (study)
        this.startTime = Date.now();
        this.timerInterval = null;
        this.submitted = false;

        this._init();
    }

    /* ── Initialization ────────────────────────────────────────── */

    _init() {
        // Set mode badge
        const badge = document.getElementById('mode-badge');
        badge.textContent = this.mode.toUpperCase();

        // Build navigator
        this._buildNavigator();

        // Show timer in exam mode
        if (this.mode === 'exam' && this.timeLimit > 0) {
            document.getElementById('timer').style.display = '';
            this._startTimer();
        }

        // Show check button only in study mode
        if (this.mode === 'study') {
            document.getElementById('check-btn').style.display = '';
        }

        // Wire up controls
        document.getElementById('prev-btn').addEventListener('click', () => this.prev());
        document.getElementById('next-btn').addEventListener('click', () => this.next());
        document.getElementById('flag-btn').addEventListener('click', () => this.toggleFlag());
        document.getElementById('check-btn').addEventListener('click', () => this.checkAnswer());
        document.getElementById('end-quiz-btn').addEventListener('click', () => this._handleEndQuiz());
        document.getElementById('cancel-submit-btn').addEventListener('click', () => {
            document.getElementById('submit-overlay').style.display = 'none';
        });
        document.getElementById('confirm-submit-btn').addEventListener('click', () => this.submit());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT' || e.target.tagName === 'TEXTAREA') return;
            if (e.key === 'ArrowRight' || e.key === 'n') this.next();
            if (e.key === 'ArrowLeft' || e.key === 'p') this.prev();
            if (e.key === 'f') this.toggleFlag();
        });

        // Render first question
        this.goTo(0);
    }

    _buildNavigator() {
        const grid = document.getElementById('nav-grid');
        grid.innerHTML = '';
        for (let i = 0; i < this.questions.length; i++) {
            const btn = document.createElement('button');
            btn.className = 'nav-btn';
            btn.textContent = i + 1;
            btn.addEventListener('click', () => this.goTo(i));
            grid.appendChild(btn);
        }
    }

    /* ── Navigation ────────────────────────────────────────────── */

    goTo(index) {
        if (index < 0 || index >= this.questions.length) return;
        this.currentIndex = index;
        this._renderQuestion();
        this._updateNav();
        this._updateControls();
    }

    next() {
        if (this.currentIndex < this.questions.length - 1) {
            this.goTo(this.currentIndex + 1);
        } else {
            this._handleEndQuiz();
        }
    }

    prev() {
        if (this.currentIndex > 0) {
            this.goTo(this.currentIndex - 1);
        }
    }

    toggleFlag() {
        const q = this.questions[this.currentIndex];
        if (this.flagged.has(q.id)) {
            this.flagged.delete(q.id);
        } else {
            this.flagged.add(q.id);
        }
        this._updateNav();
        this._updateControls();
    }

    /* ── Rendering ─────────────────────────────────────────────── */

    _renderQuestion() {
        const q = this.questions[this.currentIndex];
        const area = document.getElementById('question-area');
        const feedback = document.getElementById('feedback-area');
        feedback.style.display = 'none';

        // Meta info
        let metaHtml = '<div class="question-meta">';
        if (q.domain) metaHtml += `<span class="badge">Domain ${q.domain}</span>`;
        if (q.objective) metaHtml += `<span class="badge">Obj ${q.objective}</span>`;
        if (q.difficulty) metaHtml += `<span class="badge">${q.difficulty}</span>`;
        metaHtml += `<span class="badge">${this._typeLabel(q.type)}</span>`;
        metaHtml += '</div>';

        let html = metaHtml;

        // Question text (scenarios have separate text)
        if (q.type === 'scenario') {
            html += `<div class="scenario-text">${this._esc(q.scenario)}</div>`;
            html += this._renderScenarioParts(q);
        } else {
            html += `<div class="question-text"><span class="q-number">Q${this.currentIndex + 1}.</span>${this._esc(q.question)}</div>`;
            html += this._renderQuestionBody(q);
        }

        area.innerHTML = html;
        this._attachQuestionHandlers(q);

        // Show study mode feedback if already checked
        if (this.checked[q.id]) {
            this._showFeedback(this.checked[q.id]);
        }
    }

    _renderQuestionBody(q) {
        switch (q.type) {
            case 'multiple_choice': return this._renderMC(q);
            case 'multiple_select': return this._renderMS(q);
            case 'matching': return this._renderMatching(q);
            case 'ordering': return this._renderOrdering(q);
            case 'drag_drop': return this._renderDragDrop(q);
            case 'fill_in': return this._renderFillIn(q);
            default: return `<p>Unsupported question type: ${q.type}</p>`;
        }
    }

    _renderMC(q) {
        const selected = this.answers[q.id];
        const checkedResult = this.checked[q.id];
        return `<ul class="option-list" data-qid="${q.id}">
            ${q.options.map(opt => {
                let cls = 'option-item';
                if (selected === opt.key) cls += ' selected';
                if (checkedResult) {
                    if (opt.key === checkedResult.correct_answer) cls += ' correct-answer';
                    else if (selected === opt.key && !checkedResult.is_correct) cls += ' wrong-answer';
                }
                return `<li class="${cls}" data-key="${opt.key}">
                    <span class="option-key">${opt.key}</span>
                    <span class="option-text">${this._esc(opt.text)}</span>
                </li>`;
            }).join('')}
        </ul>`;
    }

    _renderMS(q) {
        const selected = this.answers[q.id] || [];
        const count = q.select_count || 2;
        const checkedResult = this.checked[q.id];
        return `<p style="font-size:13px;color:var(--gray-500);margin-bottom:8px">Select ${count} answers</p>
        <ul class="option-list" data-qid="${q.id}" data-select-count="${count}">
            ${q.options.map(opt => {
                let cls = 'option-item';
                if (selected.includes(opt.key)) cls += ' selected';
                if (checkedResult) {
                    const correctSet = new Set(checkedResult.correct_answer || []);
                    if (correctSet.has(opt.key)) cls += ' correct-answer';
                    else if (selected.includes(opt.key)) cls += ' wrong-answer';
                }
                return `<li class="${cls}" data-key="${opt.key}">
                    <span class="option-key">${opt.key}</span>
                    <span class="option-text">${this._esc(opt.text)}</span>
                </li>`;
            }).join('')}
        </ul>`;
    }

    _renderMatching(q) {
        const current = this.answers[q.id] || {};
        const rights = q.shuffled_rights || q.pairs.map(p => p.right);
        return `<div class="matching-grid" data-qid="${q.id}">
            ${q.pairs.map(pair => {
                return `<div class="matching-row">
                    <div class="matching-left">${this._esc(pair.left)}</div>
                    <span class="matching-arrow">&#10230;</span>
                    <select class="matching-select" data-left="${this._esc(pair.left)}">
                        <option value="">— Select —</option>
                        ${rights.map(r => `<option value="${this._esc(r)}" ${current[pair.left] === r ? 'selected' : ''}>${this._esc(r)}</option>`).join('')}
                    </select>
                </div>`;
            }).join('')}
        </div>`;
    }

    _renderOrdering(q) {
        const current = this.answers[q.id] || q.items;
        return `<ul class="ordering-list" data-qid="${q.id}">
            ${current.map((item, i) => `
                <li class="ordering-item" draggable="true" data-index="${i}">
                    <span class="ordering-handle">&#9776;</span>
                    <span class="ordering-num"></span>
                    <span class="ordering-text">${this._esc(item)}</span>
                </li>
            `).join('')}
        </ul>`;
    }

    _renderDragDrop(q) {
        const current = this.answers[q.id] || {};
        // Items not yet categorized go in the pool
        const categorized = new Set(Object.keys(current));
        const poolItems = q.items.filter(i => !categorized.has(i.text));

        return `<div class="dd-container" data-qid="${q.id}">
            <div>
                <div class="dd-pool-label">Items (drag to categories below)</div>
                <div class="dd-pool" data-category="__pool__">
                    ${poolItems.map(i => `<div class="dd-item" draggable="true" data-text="${this._esc(i.text)}">${this._esc(i.text)}</div>`).join('')}
                </div>
            </div>
            <div class="dd-categories">
                ${q.categories.map(cat => {
                    const catItems = q.items.filter(i => current[i.text] === cat);
                    return `<div class="dd-category" data-category="${this._esc(cat)}">
                        <div class="dd-category-title">${this._esc(cat)}</div>
                        <div class="dd-category-items">
                            ${catItems.map(i => `<div class="dd-item" draggable="true" data-text="${this._esc(i.text)}">${this._esc(i.text)}</div>`).join('')}
                        </div>
                    </div>`;
                }).join('')}
            </div>
        </div>`;
    }

    _renderFillIn(q) {
        const current = this.answers[q.id] || '';
        return `<div class="fill-in-wrapper" data-qid="${q.id}">
            <input type="text" class="fill-in-input" value="${this._esc(current)}"
                   placeholder="Type your answer..." autocomplete="off">
        </div>`;
    }

    _renderScenarioParts(q) {
        const currentAnswers = this.answers[q.id] || {};
        let html = '<div class="scenario-parts">';
        q.parts.forEach((part, i) => {
            html += `<div class="scenario-part" data-part-id="${part.id}">`;
            html += `<div class="scenario-part-label">Part ${String.fromCharCode(65 + i)}</div>`;
            html += `<div class="question-text">${this._esc(part.question)}</div>`;

            // Render each part's input based on its type
            const partQ = { ...part, id: part.id };
            // For scenario parts, temporarily set answer context
            const saved = this.answers[q.id];
            this.answers[q.id] = currentAnswers;
            // Build part body with a temporary qid hack
            const miniQ = { ...part, _scenario_parent: q.id };
            switch (part.type) {
                case 'multiple_choice':
                    html += this._renderMC({ ...part, id: part.id, options: part.options });
                    break;
                case 'multiple_select':
                    html += this._renderMS({ ...part, id: part.id, options: part.options });
                    break;
                case 'fill_in':
                    html += `<input type="text" class="fill-in-input scenario-fill"
                                data-part-id="${part.id}" data-parent="${q.id}"
                                value="${this._esc(currentAnswers[part.id] || '')}"
                                placeholder="Type your answer..." autocomplete="off">`;
                    break;
            }
            this.answers[q.id] = saved;
            html += '</div>';
        });
        html += '</div>';
        return html;
    }

    /* ── Event handlers ────────────────────────────────────────── */

    _attachQuestionHandlers(q) {
        if (q.type === 'multiple_choice') this._attachMCHandlers(q);
        else if (q.type === 'multiple_select') this._attachMSHandlers(q);
        else if (q.type === 'matching') this._attachMatchingHandlers(q);
        else if (q.type === 'ordering') this._attachOrderingHandlers(q);
        else if (q.type === 'drag_drop') this._attachDDHandlers(q);
        else if (q.type === 'fill_in') this._attachFillInHandlers(q);
        else if (q.type === 'scenario') this._attachScenarioHandlers(q);
    }

    _attachMCHandlers(q) {
        const list = document.querySelector(`[data-qid="${q.id}"]`);
        if (!list) return;
        list.querySelectorAll('.option-item').forEach(item => {
            item.addEventListener('click', () => {
                if (this.checked[q.id]) return; // locked after check
                list.querySelectorAll('.option-item').forEach(i => i.classList.remove('selected'));
                item.classList.add('selected');
                this.answers[q.id] = item.dataset.key;
                this._updateNav();
            });
        });
    }

    _attachMSHandlers(q) {
        const list = document.querySelector(`[data-qid="${q.id}"]`);
        if (!list) return;
        const maxSelect = parseInt(list.dataset.selectCount) || 2;
        list.querySelectorAll('.option-item').forEach(item => {
            item.addEventListener('click', () => {
                if (this.checked[q.id]) return;
                if (!this.answers[q.id]) this.answers[q.id] = [];
                const key = item.dataset.key;
                const idx = this.answers[q.id].indexOf(key);
                if (idx >= 0) {
                    this.answers[q.id].splice(idx, 1);
                    item.classList.remove('selected');
                } else {
                    if (this.answers[q.id].length >= maxSelect) return;
                    this.answers[q.id].push(key);
                    item.classList.add('selected');
                }
                this._updateNav();
            });
        });
    }

    _attachMatchingHandlers(q) {
        document.querySelectorAll(`[data-qid="${q.id}"] .matching-select`).forEach(sel => {
            sel.addEventListener('change', () => {
                if (!this.answers[q.id]) this.answers[q.id] = {};
                this.answers[q.id][sel.dataset.left] = sel.value;
                this._updateNav();
            });
        });
    }

    _attachOrderingHandlers(q) {
        const list = document.querySelector(`[data-qid="${q.id}"]`);
        if (!list) return;
        let dragItem = null;

        list.querySelectorAll('.ordering-item').forEach(item => {
            item.addEventListener('dragstart', (e) => {
                dragItem = item;
                item.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            });
            item.addEventListener('dragend', () => {
                item.classList.remove('dragging');
                list.querySelectorAll('.ordering-item').forEach(i => i.classList.remove('drag-over'));
                // Save current order
                this.answers[q.id] = [...list.querySelectorAll('.ordering-item')].map(
                    i => i.querySelector('.ordering-text').textContent
                );
                this._updateNav();
            });
            item.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                item.classList.add('drag-over');
            });
            item.addEventListener('dragleave', () => item.classList.remove('drag-over'));
            item.addEventListener('drop', (e) => {
                e.preventDefault();
                item.classList.remove('drag-over');
                if (dragItem && dragItem !== item) {
                    const items = [...list.children];
                    const fromIdx = items.indexOf(dragItem);
                    const toIdx = items.indexOf(item);
                    if (fromIdx < toIdx) list.insertBefore(dragItem, item.nextSibling);
                    else list.insertBefore(dragItem, item);
                }
            });
        });

        // Initialize answer from current order
        if (!this.answers[q.id]) {
            this.answers[q.id] = [...list.querySelectorAll('.ordering-item')].map(
                i => i.querySelector('.ordering-text').textContent
            );
        }
    }

    _attachDDHandlers(q) {
        const container = document.querySelector(`[data-qid="${q.id}"]`);
        if (!container) return;

        let dragEl = null;

        const handleDragStart = (e) => {
            dragEl = e.target;
            dragEl.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', e.target.dataset.text);
        };

        const handleDragEnd = (e) => {
            e.target.classList.remove('dragging');
            container.querySelectorAll('.dd-category, .dd-pool').forEach(z => z.classList.remove('drag-over'));
        };

        // Attach to all items
        container.querySelectorAll('.dd-item').forEach(item => {
            item.addEventListener('dragstart', handleDragStart);
            item.addEventListener('dragend', handleDragEnd);
        });

        // Drop zones: pool + categories
        const zones = container.querySelectorAll('.dd-category, .dd-pool');
        zones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                zone.classList.add('drag-over');
            });
            zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drag-over');
                if (!dragEl) return;

                const category = zone.dataset.category;
                const text = dragEl.dataset.text;
                const targetContainer = zone.querySelector('.dd-category-items') || zone;
                targetContainer.appendChild(dragEl);

                // Update answer
                if (!this.answers[q.id]) this.answers[q.id] = {};
                if (category === '__pool__') {
                    delete this.answers[q.id][text];
                } else {
                    this.answers[q.id][text] = category;
                }
                this._updateNav();
            });
        });
    }

    _attachFillInHandlers(q) {
        const input = document.querySelector(`[data-qid="${q.id}"] .fill-in-input`);
        if (!input) return;
        input.addEventListener('input', () => {
            this.answers[q.id] = input.value;
            this._updateNav();
        });
    }

    _attachScenarioHandlers(q) {
        if (!this.answers[q.id]) this.answers[q.id] = {};

        // Handle MC/MS parts within scenario
        q.parts.forEach(part => {
            if (part.type === 'multiple_choice') {
                const list = document.querySelector(`.scenario-part[data-part-id="${part.id}"] .option-list`);
                if (!list) return;
                list.querySelectorAll('.option-item').forEach(item => {
                    item.addEventListener('click', () => {
                        list.querySelectorAll('.option-item').forEach(i => i.classList.remove('selected'));
                        item.classList.add('selected');
                        this.answers[q.id][part.id] = item.dataset.key;
                        this._updateNav();
                    });
                });
                // Restore selection
                if (this.answers[q.id][part.id]) {
                    const sel = list.querySelector(`[data-key="${this.answers[q.id][part.id]}"]`);
                    if (sel) sel.classList.add('selected');
                }
            }
            if (part.type === 'fill_in') {
                const input = document.querySelector(`.scenario-fill[data-part-id="${part.id}"]`);
                if (!input) return;
                input.addEventListener('input', () => {
                    this.answers[q.id][part.id] = input.value;
                    this._updateNav();
                });
            }
        });
    }

    /* ── Study mode: check answer ──────────────────────────────── */

    async checkAnswer() {
        const q = this.questions[this.currentIndex];
        if (this.checked[q.id]) return;

        const answer = this.answers[q.id];
        if (answer === undefined || answer === null || answer === '') {
            alert('Please provide an answer before checking.');
            return;
        }

        try {
            const resp = await fetch(`/api/quiz/${this.sessionId}/check`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: q, answer }),
            });
            const result = await resp.json();
            this.checked[q.id] = result;
            this._showFeedback(result);
            this._updateNav();
            // Re-render to show correct/incorrect styling
            this._renderQuestion();
        } catch (err) {
            console.error('Check failed:', err);
        }
    }

    _showFeedback(result) {
        const area = document.getElementById('feedback-area');
        const box = document.getElementById('feedback-box');
        area.style.display = 'block';

        const isCorrect = result.is_correct;
        box.className = `feedback-box ${isCorrect ? 'correct' : 'incorrect'}`;
        box.innerHTML = `
            <span class="feedback-label">${isCorrect ? '&#10003; Correct!' : '&#10007; Incorrect'}</span>
            ${!isCorrect && result.correct_answer ? `<div><strong>Correct answer:</strong> ${this._formatAnswer(result.correct_answer)}</div>` : ''}
            ${result.feedback ? `<div class="feedback-explanation">${this._esc(result.feedback)}</div>` : ''}
            ${result.part_results ? this._renderPartFeedback(result.part_results) : ''}
        `;
    }

    _renderPartFeedback(parts) {
        return '<div style="margin-top:8px">' + parts.map((p, i) => {
            const icon = p.is_correct ? '&#10003;' : '&#10007;';
            const color = p.is_correct ? 'var(--success)' : 'var(--danger)';
            return `<div style="margin-top:4px"><span style="color:${color}">${icon}</span> Part ${String.fromCharCode(65 + i)}: ${p.feedback || (p.is_correct ? 'Correct' : 'Incorrect')}</div>`;
        }).join('') + '</div>';
    }

    /* ── Timer ──────────────────────────────────────────────────── */

    _startTimer() {
        this._updateTimerDisplay();
        this.timerInterval = setInterval(() => this._updateTimerDisplay(), 1000);
    }

    _updateTimerDisplay() {
        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        const total = this.timeLimit * 60;
        const remaining = total - elapsed;

        if (remaining <= 0) {
            clearInterval(this.timerInterval);
            this.submit();
            return;
        }

        const mins = Math.floor(remaining / 60);
        const secs = remaining % 60;
        const timerEl = document.getElementById('timer');
        timerEl.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;

        // Warnings
        timerEl.classList.remove('warning', 'danger');
        if (remaining <= 60) timerEl.classList.add('danger');
        else if (remaining <= 300) timerEl.classList.add('warning');
    }

    /* ── UI Updates ────────────────────────────────────────────── */

    _updateNav() {
        const buttons = document.querySelectorAll('.nav-btn');
        buttons.forEach((btn, i) => {
            const q = this.questions[i];
            btn.className = 'nav-btn';
            if (i === this.currentIndex) btn.classList.add('current');
            if (this.answers[q.id] !== undefined && this.answers[q.id] !== null && this.answers[q.id] !== '') {
                btn.classList.add('answered');
            }
            if (this.flagged.has(q.id)) btn.classList.add('flagged');
            if (this.checked[q.id]) {
                btn.classList.add(this.checked[q.id].is_correct ? 'correct' : 'incorrect');
            }
        });

        // Progress
        const answered = this.questions.filter(q => {
            const a = this.answers[q.id];
            return a !== undefined && a !== null && a !== '';
        }).length;
        document.getElementById('progress-text').textContent = `${this.currentIndex + 1} / ${this.questions.length}`;
        document.getElementById('progress-bar').style.width = `${(answered / this.questions.length) * 100}%`;
    }

    _updateControls() {
        const q = this.questions[this.currentIndex];
        document.getElementById('prev-btn').disabled = this.currentIndex === 0;

        const nextBtn = document.getElementById('next-btn');
        if (this.currentIndex === this.questions.length - 1) {
            nextBtn.textContent = this.mode === 'exam' ? 'Review & Submit' : 'Finish';
        } else {
            nextBtn.textContent = 'Next \u2192';
        }

        const flagBtn = document.getElementById('flag-btn');
        flagBtn.classList.toggle('active', this.flagged.has(q.id));

        const checkBtn = document.getElementById('check-btn');
        if (this.mode === 'study') {
            checkBtn.style.display = this.checked[q.id] ? 'none' : '';
        }
    }

    /* ── End / Submit ──────────────────────────────────────────── */

    _handleEndQuiz() {
        if (this.submitted) return;

        const answered = this.questions.filter(q => {
            const a = this.answers[q.id];
            return a !== undefined && a !== null && a !== '';
        }).length;
        const unanswered = this.questions.length - answered;
        const flaggedCount = this.flagged.size;

        const summary = document.getElementById('submit-summary');
        summary.innerHTML = `
            <div class="submit-summary">
                <strong>Answered: ${answered} / ${this.questions.length}</strong>
                ${unanswered > 0 ? `<strong style="color:var(--danger)">Unanswered: ${unanswered}</strong>` : ''}
                ${flaggedCount > 0 ? `<strong style="color:var(--warning)">Flagged: ${flaggedCount}</strong>` : ''}
                <p style="margin-top:8px">Are you sure you want to submit?</p>
            </div>
        `;
        document.getElementById('submit-overlay').style.display = 'flex';
    }

    async submit() {
        if (this.submitted) return;
        this.submitted = true;

        clearInterval(this.timerInterval);
        const timeSpent = Math.floor((Date.now() - this.startTime) / 1000);

        // Ensure all question IDs are represented
        const allAnswers = {};
        this.questions.forEach(q => {
            allAnswers[q.id] = this.answers[q.id] !== undefined ? this.answers[q.id] : null;
        });

        try {
            const resp = await fetch(`/api/quiz/${this.sessionId}/submit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    answers: allAnswers,
                    time_spent_seconds: timeSpent,
                }),
            });
            const data = await resp.json();
            // Clean up session storage
            sessionStorage.removeItem(`quiz_${this.sessionId}`);
            // Redirect to results
            window.location.href = `/results/${this.sessionId}`;
        } catch (err) {
            console.error('Submit failed:', err);
            this.submitted = false;
            alert('Failed to submit quiz. Please try again.');
        }
    }

    /* ── Helpers ────────────────────────────────────────────────── */

    _esc(str) {
        if (str === null || str === undefined) return '';
        const div = document.createElement('div');
        div.textContent = String(str);
        return div.innerHTML;
    }

    _typeLabel(type) {
        const labels = {
            multiple_choice: 'Multiple Choice',
            multiple_select: 'Multiple Select',
            matching: 'Matching',
            ordering: 'Ordering',
            drag_drop: 'Drag & Drop',
            fill_in: 'Fill In',
            scenario: 'Scenario',
        };
        return labels[type] || type;
    }

    _formatAnswer(answer) {
        if (Array.isArray(answer)) return answer.join(', ');
        if (typeof answer === 'object' && answer !== null) {
            return Object.entries(answer).map(([k, v]) => `${k} → ${v}`).join('; ');
        }
        return String(answer);
    }
}
