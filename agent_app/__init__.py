"""ONE-MP Read Agent package."""

from pathlib import Path

from dotenv import load_dotenv

# Reason: load agent_app/.env on package import so FOUNDRY_* env vars are
# available before any submodule (server, agent, tools) is imported. Manual
# uvicorn startup and tests both pick this up automatically.
load_dotenv(Path(__file__).parent / ".env")
