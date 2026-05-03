import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.database import init_db
from app.routers import auth, screenshots, employees
from app.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables (best-effort — for serverless, tables should exist already)
    try:
        await init_db()
        print("✅ Database initialized")
    except Exception as e:
        print(f"⚠️  init_db skipped: {e}")
    yield
    print("👋 Shutting down")


app = FastAPI(
    title="Employee Monitor API",
    version="1.0.0",
    lifespan=lifespan,
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
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(screenshots.router)
app.include_router(employees.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}

