from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.builder.graph import build_builder_graph, checkpointer_conn_string
from app.config import settings
from app.routers import auth, agents, architect, test_chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One checkpointer connection and one compiled graph for the app's lifetime.
    async with AsyncPostgresSaver.from_conn_string(checkpointer_conn_string()) as checkpointer:
        await checkpointer.setup()  # creates/migrates LangGraph's own tables
        app.state.builder_graph = build_builder_graph(checkpointer)
        yield


app=FastAPI(lifespan=lifespan)

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(architect.router)
app.include_router(test_chat.router)

@app.get("/health")
def health_check():
    return {"status":"ok", "environment": settings.environment}
