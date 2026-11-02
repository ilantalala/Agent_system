import asyncio

from app.llm.chat_model import get_chat_model
from app.models import Agent, User
from app.runtime import AgentDefinition, AgentRunner
from app.runtime.tools import DEV_TOOLS


async def main() -> None:
    # Unsaved objects, so no DB: with no stored key, development uses the .env key.
    definition = AgentDefinition(
        system_prompt="You are a helpful assistant. Keep answers short.",
        model=get_chat_model(Agent(), User()),
        tools=DEV_TOOLS,
    )
    runner = AgentRunner()  # no checkpointer: in-memory, forgotten on exit

    for text in ["What time is it right now?", "What did I ask you a moment ago?"]:
        reply = await runner.run(definition, "try:1", text)
        print(f"\nYOU:   {text}\nAGENT: {reply}")


asyncio.run(main())
