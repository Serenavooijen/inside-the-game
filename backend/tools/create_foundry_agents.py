"""
Creates (or updates) the Analyst, the Narrator and the Scout as prompt agents in Foundry Agent Service.

They use exactly the same instructions and output schemas as the code agents
(app/agents/prompts.py, app/agents/models.py), so a comparison is fair.

    cd backend
    az login
    $env:FOUNDRY_PROJECT_ENDPOINT = "https://<resource>.services.ai.azure.com/api/projects/<project>"
    $env:MODEL_ANALYST = "gpt-4.1-mini"     # deployment names in your project
    $env:MODEL_NARRATOR = "gpt-4.1-mini"
    $env:MODEL_SCOUT = "gpt-4.1-mini"
    uv run python tools/create_foundry_agents.py

Every run publishes a new version. The script prints the versions and writes them
to backend/.env.foundry-agents so you can load them before running the workflow.
`--only scout` (or `--only analyst,narrator`) publishes just those; the others keep their version.
"""

from __future__ import annotations

import os
import sys
import warnings

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from app.agents.models import AnalystDraft, ScoutDraft  # noqa: E402
from app.agents.prompts import ANALYST_INSTRUCTIONS, NARRATOR_INSTRUCTIONS, SCOUT_INSTRUCTIONS  # noqa: E402


def main() -> int:
    endpoint = os.getenv("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        print("Set FOUNDRY_PROJECT_ENDPOINT first (Foundry portal → project → Overview → Endpoint).")
        return 2
    analyst_model = os.getenv("MODEL_ANALYST", "gpt-4.1-mini")
    narrator_model = os.getenv("MODEL_NARRATOR", "gpt-4.1-mini")
    analyst_name = os.getenv("FOUNDRY_ANALYST_AGENT", "itg-analyst")
    narrator_name = os.getenv("FOUNDRY_NARRATOR_AGENT", "itg-narrator")
    scout_model = os.getenv("MODEL_SCOUT", analyst_model)
    scout_name = os.getenv("FOUNDRY_SCOUT_AGENT", "itg-scout")

    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient, to_prompt_agent
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    warnings.filterwarnings("ignore", message=".*to_prompt_agent is experimental.*")
    cred = DefaultAzureCredential()
    project = AIProjectClient(endpoint=endpoint, credential=cred)

    def publish(name: str, model: str, instructions: str, description: str, response_format=None) -> str:
        client = FoundryChatClient(project_endpoint=endpoint, model=model, credential=cred)
        options = {"response_format": response_format} if response_format else None
        agent = Agent(client=client, name=name, instructions=instructions, default_options=options)
        definition = to_prompt_agent(agent)
        version = project.agents.create_version(agent_name=name, definition=definition, description=description)
        print(f"✓ {name}: version {version.version} (model {model})")
        return str(version.version)

    # --only scout: publish just these agents; the others keep the version in .env.foundry-agents.
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else {"analyst", "narrator", "scout"}
    env_path = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".env.foundry-agents"))
    env = {}
    if os.path.exists(env_path):
        env = dict(line.strip().split("=", 1) for line in open(env_path) if "=" in line)
    env.update(MODEL_PROVIDER="foundry-agents", FOUNDRY_PROJECT_ENDPOINT=endpoint)

    if "analyst" in only:
        env.update(FOUNDRY_ANALYST_AGENT=analyst_name, FOUNDRY_ANALYST_AGENT_VERSION=publish(
            analyst_name, analyst_model, ANALYST_INSTRUCTIONS,
            "Inside the Game · Analyst: picks 2–3 claims from the FactSheet, each citing fact ids.", AnalystDraft))
    if "narrator" in only:
        env.update(FOUNDRY_NARRATOR_AGENT=narrator_name, FOUNDRY_NARRATOR_AGENT_VERSION=publish(
            narrator_name, narrator_model, NARRATOR_INSTRUCTIONS,
            "Inside the Game · Narrator: turns checked claims into 1–3 sentences for fans."))
    if "scout" in only:
        env.update(FOUNDRY_SCOUT_AGENT=scout_name, FOUNDRY_SCOUT_AGENT_VERSION=publish(
            scout_name, scout_model, SCOUT_INSTRUCTIONS,
            "Inside the Game · Scout: opposition analyst; 2–3 tactical observations with consequence, citing fact ids.",
            ScoutDraft))

    with open(env_path, "w") as f:
        f.writelines(f"{k}={v}\n" for k, v in env.items())
    print(f"\nWrote {env_path}. Compare both set-ups with:\n"
          f"  uv run python -m app.agents.run_fixtures --compare foundry,foundry-agents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
