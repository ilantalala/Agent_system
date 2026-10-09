from fastapi import FastAPI
from app.config import settings
from app.routers import auth, agents, architect, test_chat


app=FastAPI()

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(architect.router)
app.include_router(test_chat.router)

@app.get("/health")
def health_check():
    return {"status":"ok", "environment": settings.environment}
