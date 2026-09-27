from fastapi import FastAPI
from app.config import settings
from app.routers import auth, agents, architect

app=FastAPI()

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(architect.router)

@app.get("/health")
def health_check():
    return {"status":"ok", "environment": settings.environment}
