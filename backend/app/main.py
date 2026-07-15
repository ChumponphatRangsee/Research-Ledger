from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analysis, health, portfolio, screener
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description="AI orchestration and financial data crunching for InvestFlow-AI",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(screener.router, prefix="/api/screener", tags=["screener"])
    app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"])
    app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])

    return app


app = create_app()
