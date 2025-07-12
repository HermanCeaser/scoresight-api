#!/usr/bin/env python3
"""
FastAPI application entry point for ScoreSight.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "main:app",  # Use the new main module
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
