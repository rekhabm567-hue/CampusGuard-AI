# CampusGuard AI: LLM Hallucination Firewall for Enterprise Search

A secure, evidence-grounded question-answering system for college policy
documents. It reduces unsupported LLM answers through authorization-aware
retrieval, source verification, conflict detection and abstention.

**Status:** work in progress (Streamlit prototype being refactored).
See `PROGRESS.md` for the checklist.

## Setup (Windows, PowerShell, Python 3.10)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
copy .env.example .env
```

Edit `.env` and set the four `SEED_*_PASSWORD` values (at least 8 characters).
Never commit `.env`.

## Run

```powershell
python -m app.database.seed
streamlit run main.py
```

## Test

```powershell
python -m pytest -q
```

## Project layout

- `app/auth`: users, authentication, authorization
- `app/retrieval`: query understanding, BM25, FAISS, hybrid search, reranking
- `app/firewall`: claim extraction, evidence matching, contradiction detection
- `app/llm`: answer generation
- `app/documents`: loading, chunking, metadata, registry
- `data/`: local database, documents and index (ignored by Git)

## Rollback

Git tag `baseline-2026-10-10` marks the original prototype.