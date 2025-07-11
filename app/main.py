from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.v1 import router as api_v1_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="ScoreSight API", 
        version="1.0.0",
        description="API for automated exam grading and analysis using AI"
    )

    # CORS configuration
    origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(api_v1_router, prefix="/api/v1")
    
    @app.get("/")
    async def root():
        return {"message": "ScoreSight API", "version": "1.0.0", "status": "running"}
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}

    return app
