# Offsite Continuation Handoff - 2026-07-15

## Purpose

This note is the working checkpoint for continuing the Busan local-product support work from a non-office PC. It records the current GitHub baseline, production separation rules, and the minimum commands needed to resume work without depending on this local desktop only.

## Repository Boundaries

### Current operating advisor / vendor recommendation repo

- Local path: `C:\Users\COMTREE\Desktop\busanproduct-advisor`
- GitHub: `https://github.com/doors1118-sketch/busanproduct-advisor.git`
- Current branch: `codex/vendor-api-v2-handoff-20260524`
- Production server path: `/opt/advisor`
- Public vendor UI: `https://busanproduct.co.kr/vendor-ui/`
- Main production files mirrored into this repo on 2026-07-15:
  - `app/api_server.py`
  - `app/company_db.py`
  - `frontend/vendor/index.html`
  - `frontend/vendor/app.js`
  - `frontend/vendor/styles.css`

### V2 legal interpretation / intelligent contract support repo

- Local path: `C:\Users\COMTREE\Desktop\busan-local-purchase-advisor-v2`
- GitHub: `https://github.com/doors1118-sketch/busan-local-purchase-advisor-v2.git`
- Current branch observed on 2026-07-15: `codex/vendor-api-v2-handoff-20260524`
- Use this repo for non-office work on legal interpretation, RAG/LLM answer flow, and future integrated service design.
- Do not treat this as an automatic production deploy target. Production deployment remains a separate server operation.

### Older RAG lab / reference repo

- Local path: `C:\Users\COMTREE\Desktop\busanproduct-advisor-rag-v2`
- Current branch observed on 2026-07-15: `codex/rag-v2-lab`
- Use as reference only unless a specific task says to continue the lab branch.

## Resume From Another PC

For the operating advisor/vendor recommendation repo:

```powershell
git clone https://github.com/doors1118-sketch/busanproduct-advisor.git
cd busanproduct-advisor
git checkout codex/vendor-api-v2-handoff-20260524
git pull
```

For the V2 legal interpretation repo:

```powershell
git clone https://github.com/doors1118-sketch/busan-local-purchase-advisor-v2.git
cd busan-local-purchase-advisor-v2
git checkout codex/vendor-api-v2-handoff-20260524
git pull
```

## What GitHub Does Not Carry

GitHub does not include live secrets or production data:

- `.env`
- NCP/Object Storage keys
- SSH private keys
- live SQLite databases
- production cache directories
- server-only backup archives

If a feature needs real DB behavior, verify against the server copy or a sanitized DB snapshot. Do not assume a clean clone has the production DB.

## Current Vendor Recommendation Baseline

As of this checkpoint:

- Backend API includes `/vendor-recommendations/search`.
- Backend API includes `/vendor-recommendations/search.xlsx`.
- Backend API includes `/vendor-recommendations/{company_id}/contract-history`.
- Search response includes purchase-route guidance, item-policy summary, zero-result status, candidate evidence, and contract-history fields when the DB view exists.
- Frontend is a standalone vendor UI under `frontend/vendor/`, served in production at `/vendor-ui/`.
- The production UI no longer uses a left sidebar and now focuses on search, purchase-route summary, candidate cards, evidence badges, and XLSX download.
- Targeted API regression check passed locally:

```text
python -m pytest tests/test_vendor_api_endpoints.py -q
61 passed
```

## Work Split

Vendor recommendation and deterministic DB-backed candidate selection:

- Continue in `busanproduct-advisor` unless the task is explicitly V2-only.
- Candidate vendors must come from the internal DB/API. Do not let the LLM invent vendor candidates.
- LLM can explain, summarize, and guide, but should not be the source of supplier existence.

Legal interpretation / RAG / contract-protection guidance:

- Continue in `busan-local-purchase-advisor-v2`.
- Keep it separated from the production `/opt/advisor` service until a deployment plan is made.
- Reuse monitoring/vendor DB data only through explicit API/DB interfaces, not by copying assumptions into prompts.

## Production Deployment Reminder

Committing and pushing to GitHub is not deployment.

Production changes still require a separate server step, normally against `/opt/advisor`, with backup first and service restart only after syntax/API checks. Avoid relying on the old 5-minute auto-deploy cron unless it has been explicitly reviewed and re-enabled.

