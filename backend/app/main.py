from fastapi import FastAPI
from app.config import settings


app=FastAPI()

@app.get("/health")
def health_check():
    return {"status":"ok", "environment": settings.environment}
