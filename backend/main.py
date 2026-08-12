import logging

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import availability, businesses, coverage, employees, schedules, webhooks_twilio
from core.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="AI-optimized, SMS-driven employee scheduling",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(businesses.router, prefix="/api")
app.include_router(employees.router, prefix="/api")
app.include_router(coverage.router, prefix="/api")
app.include_router(availability.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(webhooks_twilio.router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok"}
