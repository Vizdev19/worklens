import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, screenshots, employees, orgs
from app.config import get_settings

settings = get_settings()


# NOTE: We do NOT run init_db() in a lifespan handler.
# Tables are created once via `python -m scripts.create_admin` (which calls
# init_db() and seeds an admin). Running it on every serverless cold start
# costs 1-2s per request — not worth it for a no-op.
app = FastAPI(
    title="Employee Monitor API",
    version="1.0.0",
)

# Allowed origins from env var: comma-separated list
# In dev: http://localhost:3000
# In prod: https://employee-monitor-dashboard.vercel.app
allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
).split(",")

# Also allow all Vercel preview deployments via regex (e.g. ...-lyart.vercel.app)
# Tighten this later when you have a custom domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allowed_origins if o.strip()],
    allow_origin_regex=r"https://employee-monitor-dashboard.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(screenshots.router)
app.include_router(employees.router)
app.include_router(orgs.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}

