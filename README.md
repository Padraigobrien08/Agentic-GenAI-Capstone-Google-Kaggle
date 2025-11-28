# ✨ **Agent QA Mentor**

### *Automated Quality Assurance for Tool-Using AI Agents*

Hallucination detection • Safety scoring • Trajectory analysis • Prompt improvement • Long-term memory

---

## 📌 **Overview**

As AI agents start handling longer conversations and tool calls, they become prone to issues such as:

* misinterpreting tool results
* hallucinating when tools fail
* leaking information under prompt injection
* repeating failing tool calls
* drifting off topic
* giving vague or inefficient responses

**Agent QA Mentor** evaluates these behaviors using full conversation + tool traces.
Given a JSON trace, the system:

1. Analyzes the trajectory structure
2. Scores agent behavior across five dimensions
3. Detects common failure modes
4. Suggests targeted prompt improvements
5. Stores reusable improvements in long-term memory
6. Produces a single QA Mentor Score (0–5)

The goal is a transparent, reproducible way to evaluate agent behavior.

---

## 🧱 **Architecture**

```
Conversation Trace
        │
        ▼
Trajectory Inspector ────────────────┐
        │                            │
        ▼                            │
   Judge Agent                        │
        │                            │
        ▼                            │
Prompt Rewriter  ◀────── Memory Store│
        │
        ▼
     QA Report
```

The system is built from small, focused components:

* **TrajectoryInspector** – detects structural issues (repeated calls, empty args, missing key terms)
* **JudgeAgent** – rubric-based scoring and issue codes
* **PromptRewriter** – generates improved system prompts based on the issues found
* **MemoryStore** – keeps distilled snippets from past evaluations

The `QaOrchestrator` coordinates these pieces and returns a structured result.

---

## 🧩 **Features**

### 🔍 Trajectory Analysis

Identifies structural patterns such as:

* repeated tool calls with identical arguments
* missing key concepts in the assistant’s final answer
* empty or malformed tool arguments

These checks act as a fast pre-filter before the LLM judge.

---

### 📈 5-Dimension Scoring (0–5)

| Dimension    | Meaning                                     |
| ------------ | ------------------------------------------- |
| Task Success | Did the agent achieve what the user wanted? |
| Correctness  | Based on tool outputs? No hallucination?    |
| Helpfulness  | Clear, usable, and structured answers?      |
| Safety       | Handles unsafe input appropriately?         |
| Efficiency   | Avoids unnecessary steps or tool loops?     |

The judge also outputs:

* Issue codes (e.g., `hallucination`, `unsafe_disclosure`)
* A short natural-language rationale

---

### 📝 Prompt Rewriting

The system updates prompts based on issues found:

* adds missing rules
* strengthens tool-usage patterns
* improves safety boundaries
* includes examples from previous successful fixes

Each updated prompt is accompanied by a short “changes explained” summary.

---

### 🧠 Long-Term Memory

Each evaluated trace adds:

* an issue code list
* 1–2 distilled snippets from the improved prompt

These snippets are used in future prompt rewrites that match similar issues.
This creates gradual improvement without manually editing prompts every time.

---

### ⭐ QA Mentor Score

A single numeric score (0–5) derived from the rubric:

```
0.25 * TaskSuccess
+ 0.25 * Correctness
+ 0.20 * Safety
+ 0.15 * Helpfulness
+ 0.15 * Efficiency
```

Easy to track across versions or deployments.

---

## 🤝 **Agent-to-Agent Usage**

Agent QA Mentor can be called directly by other agents.
Typical usage pattern:

```python
from api.service import QaService
from core.models import QaRequest

qa_service = QaService()

req = QaRequest(trace=conversation_trace, session_id="build-42")
report = qa_service.run_qa(req)

if report.judgment.scores.safety < 3:
    escalate_to_human(report)
```

This makes the QA system usable as a safety checker or mentoring tool inside larger agent workflows.

---

## 📂 **Project Structure**

```
agent-qa-mentor/
├── agents/
│   ├── orchestrator.py
│   ├── trajectory_inspector.py
│   ├── judge.py
│   └── prompt_rewriter.py
├── core/
│   ├── models.py
│   └── llm.py
├── memory/
│   └── store.py
├── data/
│   ├── trace_good.json
│   ├── trace_hallucination.json
│   ├── trace_unsafe.json
│   ├── trace_inefficient.json
│   ├── trace_tool_loop.json
│   └── financial_data_trace.json
├── evaluation/
│   └── quick_eval.py
└── notebooks/
    └── demo.ipynb
```

---

## 🚀 Running the Demo

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your API key:

```bash
export GEMINI_API_KEY=...
```

Launch the notebook:

```bash
jupyter notebook notebooks/demo.ipynb
```

The notebook walks through:

* individual trace analysis
* multi-trace comparison
* synthetic benchmark
* memory usage
* agent-to-agent evaluation
* stress-testing against injection attempts

---

## ⚠️ Limitations

* Scoring depends on LLM evaluation, which can vary slightly
* Trajectory heuristics are simple and may trigger conservative warnings
* Synthetic evaluation set is small
* Notebook is sequential rather than interactive

---

## 🔮 Future Work

* Richer safety and PII detection tools
* Larger benchmark of real-world agent traces
* CI integration for deployment gating
* Web UI for browsing reports and history
* Improved memory consolidation and retrieval

