# Employee Monitor — Setup & Workflow

A workforce monitoring system that captures employee screenshots periodically and lets admins view them through a web dashboard.

---

## 1. Architecture

```
┌──────────────────┐         ┌──────────────────┐
│  Employee Laptop │         │   Admin Browser  │
│   (Agent — .py)  │         │    (Dashboard)   │
└────────┬─────────┘         └────────┬─────────┘
         │ HTTPS                      │ HTTPS
         └──────────┬─────────────────┘
                    ▼
         ┌──────────────────────┐
         │   Backend API        │
         │   (FastAPI)          │
         │   on Vercel          │
         └──────────┬───────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │   Supabase           │
         │ ┌──────────────────┐ │
         │ │  PostgreSQL      │ │  ← users, screenshots, refresh_tokens
         │ └──────────────────┘ │
         │ ┌──────────────────┐ │
         │ │  Storage bucket  │ │  ← screenshot files
         │ └──────────────────┘ │
         └──────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology |
|---|---|
| Agent (employee laptop) | Python 3.9+, `mss` for screenshots, `keyring` for token storage, `pystray` for tray icon |
| Backend API | FastAPI, SQLAlchemy 2.0 async, asyncpg, JWT auth |
| Database | Supabase Postgres (via PgBouncer transaction pooler) |
| Storage | Supabase Storage bucket (`screenshots`) |
| Dashboard | Next.js 14 (App Router), TanStack Query, TailwindCSS |
| Auth | JWT access tokens (60 min) + refresh tokens (30 days) |
| Hosting | Vercel (both backend + dashboard), GitHub auto-deploy |

---

## 3. Repository Layout

```
employee-monitor/                  ← single GitHub repo (monorepo)
├── backend/                       ← FastAPI on Vercel
│   ├── app/
│   │   ├── routers/               ← /auth, /employees, /screenshots
│   │   ├── auth.py                ← password hashing + JWT
│   │   ├── config.py              ← env settings
│   │   ├── database.py            ← async SQLAlchemy + PgBouncer config
│   │   ├── models.py              ← User, Screenshot, RefreshToken
│   │   ├── schemas.py             ← Pydantic request/response shapes
│   │   └── storage.py             ← Supabase Storage client
│   ├── scripts/
│   │   ├── create_admin.py        ← seeds first admin
│   │   └── create_employee.py     ← creates employee accounts
│   ├── main.py                    ← FastAPI app entry
│   ├── requirements.txt
│   ├── vercel.json                ← Vercel build config
│   └── .env                       ← (gitignored) local secrets
│
├── dashboard/                     ← Next.js on Vercel
│   ├── app/
│   │   ├── login/                 ← admin login page
│   │   └── dashboard/
│   │       ├── page.tsx           ← overview
│   │       ├── employees/         ← list + per-employee timeline
│   │       └── screenshots/       ← all screenshots, filterable
│   ├── components/
│   │   └── ScreenshotModal.tsx    ← lightbox viewer
│   ├── lib/
│   │   └── api.ts                 ← typed API client w/ token refresh
│   └── package.json
│
└── agent/                         ← runs on each laptop
    ├── main.py                    ← scheduler entry
    ├── capture.py                 ← screenshot logic (mss)
    ├── uploader.py                ← HTTP upload + retry queue
    ├── auth.py                    ← keychain-based token storage
    ├── login_ui.py                ← first-run login window
    ├── tray.py                    ← system tray icon
    └── startup/                   ← per-OS auto-start helpers
```

---

## 4. What's Deployed

| Component | URL | Notes |
|---|---|---|
| Backend API | `https://employee-monitor-api.vercel.app` | Auto-deploys from `main` branch |
| Dashboard | `https://employee-monitor-dashboard-lyart.vercel.app` | Auto-deploys from `main` branch |
| Database | Supabase project `snztvgmgdczmmdkjvgsl` | Region: ap-south-1 (Mumbai) |
| Storage | Supabase bucket `screenshots` | Private bucket |

---

## 5. Environment Variables

### Backend (`employee-monitor-api`)

Set in Vercel → Settings → Environment Variables:

| Name | Purpose |
|---|---|
| `DATABASE_URL` | PgBouncer pooler URL with `+asyncpg` driver and URL-encoded password |
| `SUPABASE_URL` | `https://<project>.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Service role key (full access) |
| `SUPABASE_BUCKET` | `screenshots` |
| `SECRET_KEY` | JWT signing key (32 random bytes) |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `30` |
| `ALLOWED_ORIGINS` | Comma-separated dashboard URLs (regex also catches `*.vercel.app`) |
| `APP_NAME` | `EmployeeMonitor` |
| `ENVIRONMENT` | `production` |

### Dashboard (`employee-monitor-dashboard`)

| Name | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://employee-monitor-api.vercel.app` |

---

## 6. The Setup Journey — What We Did

### Phase 1: Infrastructure
1. Created Supabase project (PostgreSQL + Storage + 500 MB free)
2. Generated JWT `SECRET_KEY` via `openssl rand -hex 32`
3. Created GitHub repo, pushed monorepo (backend + dashboard + agent)

### Phase 2: Backend
1. Built FastAPI app with auth, employees, and screenshots routers
2. Added `vercel.json` to configure Python serverless build
3. Imported repo to Vercel as project A — root directory `backend`
4. Set all env vars on Vercel
5. Deployed → `/health` returned 200 ✅

### Phase 3: Database Bootstrap
1. Ran `python -m scripts.create_admin` from local machine
2. This created tables (`users`, `screenshots`, `refresh_tokens`) and the first admin
3. Verified login via curl against the production API

### Phase 4: Dashboard
1. Built Next.js dashboard with login, overview, employees list, timeline view, screenshot modal
2. Imported same repo to Vercel as project B — root directory `dashboard`
3. Set `NEXT_PUBLIC_API_URL` env var
4. Deployed → got URL `employee-monitor-dashboard-lyart.vercel.app`

### Phase 5: Connecting Dashboard ↔ Backend
1. Updated backend `ALLOWED_ORIGINS` to include the dashboard URL
2. Added permissive CORS regex for any `*.vercel.app` origin (preview deployments)
3. Redeployed backend → dashboard login worked end-to-end ✅

---

## 7. Issues Hit & How They Were Fixed

| Problem | Root cause | Fix |
|---|---|---|
| `nodename nor servname provided` | Supabase direct connection is IPv6-only on free plan | Use the **transaction pooler URL** (port 6543, IPv4) |
| `prepared statement "__asyncpg_stmt_3__" already exists` | PgBouncer transaction mode doesn't support fixed prepared statement names | Upgrade `asyncpg` to 0.30.0 + use `prepared_statement_name_func` with UUID-based names |
| `error reading bcrypt version` | passlib incompatibility with bcrypt 4.x | Drop passlib, use `bcrypt` directly |
| `extra inputs not permitted` (pydantic) | Settings rejected unknown env vars | Added `extra="ignore"` and `allowed_origins` field |
| `Could not parse SQLAlchemy URL` | `.env` had `DATABASE_URL=` prefix duplicated in value | Cleaned up `.env` line |
| Login worked via curl but failed in browser | CORS preflight rejected | Added dashboard URL to `ALLOWED_ORIGINS` + permissive regex |
| Hobby plan deploy failed | `vercel.json` cron ran every 5 min (Pro only) | Removed cron block (not needed yet) |

---

## 8. Daily Workflow

### To add a new employee
```bash
cd backend
python -m scripts.create_employee
# enter email, name, password
```
Hand the credentials to the employee — they'll use them in the agent.

### To run the agent on an employee laptop
```bash
cd agent
cp .env.example .env
# set SERVER_URL=https://employee-monitor-api.vercel.app
pip install -r requirements.txt
python main.py
```
- First launch: prompts for credentials, stores in OS keychain
- Subsequent launches: starts silently, captures every 10 minutes
- Tray icon shows monitoring status

### To view screenshots as admin
1. Open `https://employee-monitor-dashboard-lyart.vercel.app`
2. Log in with admin credentials
3. Navigate:
   - **Overview** — recent activity at a glance
   - **Employees** — list of all team members
   - **Employees → click one** — daily timeline + thumbnail grid
   - **Screenshots** — all screenshots, filterable by employee

### To deploy code changes
```bash
git add .
git commit -m "..."
git push
```
Both Vercel projects auto-deploy from `main`. No manual step needed.

---

## 9. Auth Flow

```
Employee opens agent first time
        │
        ▼
Login UI: email + password
        │
        ▼
POST /auth/login
        │
        ▼
Backend verifies password (bcrypt)
        │
        ▼
Returns access_token (1h) + refresh_token (30d)
        │
        ▼
Agent stores tokens in OS keychain
        │
        ▼
Every screenshot upload → Authorization: Bearer <access_token>
        │
        ▼
Access token expires → use refresh token silently → new access token
```

Same flow works for the dashboard — refresh tokens are stored in `localStorage` (single-user phase; will move to httpOnly cookies later).

---

## 10. Security Posture (Current)

| Area | Status | Notes |
|---|---|---|
| HTTPS | ✅ | Enforced by Vercel |
| Password hashing | ✅ | bcrypt with 72-byte truncation |
| JWT signed | ✅ | HS256 with random 32-byte key |
| Refresh tokens | ✅ | Stored in DB, revocable on logout |
| CORS | ✅ | Restricted to dashboard origins |
| `.env` files | ✅ | Gitignored, not committed |
| Storage bucket | ✅ | Private; uses signed URLs (1h expiry) |
| Rate limiting | ❌ | Not yet — add when scaling |
| 2FA | ❌ | Not yet |
| Audit log | ❌ | Not yet — single-admin phase |

---

## 11. Scaling Roadmap

### When you onboard a 2nd company
- Add `Organization` table with `organization_id` foreign keys everywhere
- Per-org settings (capture interval, retention, working hours)
- Invitation system for adding employees

### When you start charging
- Stripe customer per organization
- Plan-based seat limits
- Auto-renewal & dunning emails

### When traffic grows
- Migrate backend from Vercel to Railway (persistent server)
- Background workers for thumbnail generation
- Lifecycle policies on storage (hot → cold → delete)
- Read replicas for analytics queries

---

## 12. Quick Reference Commands

```bash
# Local backend dev
cd backend && uvicorn main:app --reload

# Local dashboard dev
cd dashboard && npm run dev

# Create admin
cd backend && python -m scripts.create_admin

# Create employee
cd backend && python -m scripts.create_employee

# Test production API
curl https://employee-monitor-api.vercel.app/health

# Tail Vercel logs
# (use the Vercel dashboard → Logs tab)
```

---

## 13. Key URLs

| What | Where |
|---|---|
| Production dashboard | https://employee-monitor-dashboard-lyart.vercel.app |
| Production API | https://employee-monitor-api.vercel.app |
| API health check | https://employee-monitor-api.vercel.app/health |
| API docs (FastAPI auto-generated) | https://employee-monitor-api.vercel.app/docs |
| Supabase project | https://supabase.com/dashboard/project/snztvgmgdczmmdkjvgsl |
| GitHub repo | (your repo URL) |
| Vercel projects | https://vercel.com/dashboard |

---

## 14. Status

✅ Backend deployed and healthy
✅ Database initialized with admin user
✅ Dashboard deployed and connected
✅ Login flow working end-to-end
⬜ Storage bucket created
⬜ Agent tested end-to-end with production
⬜ First screenshots flowing through

Next milestone: **run the agent against production and see screenshots appear in the dashboard.**
