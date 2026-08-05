# ai-scheduler

AI-optimized, SMS-driven employee scheduling. Employees submit availability by text; a manager reviews an AI-drafted weekly schedule (a constraint solver enforces coverage/labor rules, an LLM layer weighs skill fit, reliability, and manager notes) and publishes it, which instantly texts each employee their shifts plus a link to their full schedule.

Multi-tenant from day one; v1 targets a single-location restaurant business.

## Stack

- **Backend**: FastAPI + SQLAlchemy + Postgres, Alembic migrations, OR-Tools (CP-SAT) for the scheduling solver, Twilio for SMS, APScheduler for recurring jobs.
- **Frontend**: Next.js (App Router) + Tailwind, Supabase auth for managers. Employees have no login — phone-number identity only, schedule view via a signed link.

## Local setup

```bash
docker compose up -d          # Postgres

cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in secrets
uvicorn main:app --reload --port 8000

cd ../frontend
npm install
cp .env.local.example .env.local   # fill in secrets (added in Phase 1)
npm run dev
```

## Project status

See `/Users/yusuf/.claude/plans/here-is-the-repo-eventual-haven.md` for the full implementation plan and phased build order. Currently: Phase 0 (bootstrap) in progress.
