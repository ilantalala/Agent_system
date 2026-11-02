from datetime import datetime, timezone

from langchain_core.tools import tool


@tool
def get_current_time() -> str:
    """Get the current date and time in UTC, in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# Only for exercising the tool loop until the Tool Registry (Epic 11)
# decides which tools an agent gets.
DEV_TOOLS = [get_current_time]
