"""
Model adapter. One switch, MODEL_PROVIDER, picks where the agents run:

    github          Agents in code, models on GitHub Models (free, for development).
                    Needs GITHUB_TOKEN (PAT with models:read).
    foundry         Agents in code, models in Microsoft Foundry (FoundryChatClient).
                    Needs FOUNDRY_PROJECT_ENDPOINT and a login (az login / managed identity).
    foundry-agents  Agents hosted in Foundry Agent Service (prompt agents, visible in the portal).
                    Create them first with tools/create_foundry_agents.py, then set
                    FOUNDRY_ANALYST_AGENT(_VERSION), FOUNDRY_NARRATOR_AGENT(_VERSION) and,
                    for the tactical analysis, FOUNDRY_SCOUT_AGENT(_VERSION); for the
                    translations FOUNDRY_TRANSLATOR_AGENT(_VERSION).
    offline         No model at all: deterministic text from the facts. For tests, CI and demos.

Model names for the code agents: MODEL_ANALYST, MODEL_NARRATOR, MODEL_SCOUT, MODEL_TRANSLATOR (deployment names on Foundry).
In every case the workflow, the fact-check and the fallback stay the same, so the
providers can be compared like for like (run_fixtures --compare).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol

from app.contracts import TacticalFactSheet

from .models import AnalystDraft, Claim, FactSheet, ScoutDraft, TranslationDraft
from .prompts import ANALYST_INSTRUCTIONS, NARRATOR_INSTRUCTIONS, SCOUT_INSTRUCTIONS, TRANSLATOR_INSTRUCTIONS

GITHUB_MODELS_URL = "https://models.github.ai/inference"


class ModelClient(Protocol):
    name: str

    async def draft(self, sheet: FactSheet, prompt: str) -> tuple[AnalystDraft, int | None]: ...

    def narrate(self, sheet: FactSheet, claims: list[Claim], prompt: str) -> AsyncIterator[str]: ...

    # Optional: the Scout (tactical analysis). Models without it get the template fallback.
    # async def scout(self, sheet: TacticalFactSheet, prompt: str) -> tuple[ScoutDraft, int | None]: ...
    # Optional: the Translator. Models without it keep the English text.
    # async def translate(self, lang: str, texts: list[str], prompt: str) -> tuple[TranslationDraft, int | None]: ...


class NoScoutAgent(RuntimeError):
    """The model set-up has no Scout agent (e.g. foundry-agents without FOUNDRY_SCOUT_AGENT_VERSION)."""


class NoTranslatorAgent(RuntimeError):
    """The model set-up has no Translator agent (e.g. foundry-agents without FOUNDRY_TRANSLATOR_AGENT_VERSION)."""


# ---------------------------------------------------------------- shared: two Agent Framework agents


def _tokens(resp: Any) -> int | None:
    usage = getattr(resp, "usage_details", None)
    if usage is None:
        try:
            usage = resp.to_dict().get("usage_details")
        except Exception:
            usage = None
    if not usage:
        return None
    get = usage.get if isinstance(usage, dict) else lambda k, d=None: getattr(usage, k, d)
    total = get("total_token_count") or get("total_tokens")
    if total:
        return int(total)
    parts = [get("input_token_count"), get("output_token_count")]
    return int(sum(p for p in parts if p)) or None


def _parse_draft(resp: Any, model: type = AnalystDraft) -> Any:
    value = resp.value
    if isinstance(value, model):
        return value
    if isinstance(value, dict):
        return model.model_validate(value)
    # Some models / hosted agents return the JSON as plain text.
    text = resp.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return model.model_validate(json.loads(text))


@dataclass
class AgentPairModel:
    """An Analyst agent and a Narrator agent, wherever they run."""

    name: str
    analyst: Any
    narrator: Any
    # Code agents get the output schema per call; hosted agents have it in their Foundry definition.
    pass_response_format: bool = True
    credential: Any = None
    _closers: list = field(default_factory=list)
    scout_agent: Any = None
    translator: Any = None

    async def warmup(self) -> None:
        """Fetch the login token before the first moment, so it does not eat into the 6 s deadline.

        Call this once at start-up (run_fixtures does; the FastAPI app should do it in its lifespan)."""
        if self.credential is not None:
            for scope in TOKEN_SCOPES:
                await self.credential.get_token(scope)
        # One tiny call per agent opens the HTTPS connections, so the first real moment is not slower.
        import asyncio

        async def ping(agent):
            try:
                await agent.run("Warm-up call. Reply with: ok")
            except Exception:
                pass

        await asyncio.gather(*(ping(a) for a in (self.analyst, self.narrator, self.scout_agent, self.translator) if a is not None))

    async def draft(self, sheet: FactSheet, prompt: str) -> tuple[AnalystDraft, int | None]:
        options = {"response_format": AnalystDraft} if self.pass_response_format else None
        resp = await self.analyst.run(prompt, options=options)
        return _parse_draft(resp), _tokens(resp)

    async def scout(self, sheet: TacticalFactSheet, prompt: str) -> tuple[ScoutDraft, int | None]:
        if self.scout_agent is None:
            raise NoScoutAgent(f"No Scout agent in the {self.name} set-up")
        options = {"response_format": ScoutDraft} if self.pass_response_format else None
        resp = await self.scout_agent.run(prompt, options=options)
        return _parse_draft(resp, ScoutDraft), _tokens(resp)

    async def translate(self, lang: str, texts: list[str], prompt: str) -> tuple[TranslationDraft, int | None]:
        if self.translator is None:
            raise NoTranslatorAgent(f"No Translator agent in the {self.name} set-up")
        options = {"response_format": TranslationDraft} if self.pass_response_format else None
        resp = await self.translator.run(prompt, options=options)
        return _parse_draft(resp, TranslationDraft), _tokens(resp)

    async def narrate(self, sheet: FactSheet, claims: list[Claim], prompt: str) -> AsyncIterator[str]:
        # Some clients (Foundry's Responses API) send the deltas and then the full text once more
        # at the end. Only pass on what is new, so the text is never doubled.
        seen = ""
        async for update in self.narrator.run(prompt, stream=True):
            chunk = update.text or ""
            if not chunk:
                continue
            if seen and chunk.startswith(seen):
                chunk = chunk[len(seen):]
            elif seen and len(chunk) > 20 and seen.endswith(chunk):
                continue
            if chunk:
                seen += chunk
                yield chunk


# ---------------------------------------------------------------- builders


def openai_compatible(name: str, base_url: str, api_key: str, analyst_model: str, narrator_model: str,
                      scout_model: str | None = None, translator_model: str | None = None) -> AgentPairModel:
    """Agents in code on any OpenAI-compatible chat-completions endpoint (GitHub Models)."""
    from agent_framework import Agent
    from agent_framework.openai import OpenAIChatCompletionClient

    def client(model: str):
        return OpenAIChatCompletionClient(model=model, api_key=api_key, base_url=base_url)

    return AgentPairModel(
        name=name,
        analyst=Agent(client=client(analyst_model), name="Analyst", instructions=ANALYST_INSTRUCTIONS),
        narrator=Agent(client=client(narrator_model), name="Narrator", instructions=NARRATOR_INSTRUCTIONS),
        scout_agent=Agent(client=client(scout_model or analyst_model), name="Scout", instructions=SCOUT_INSTRUCTIONS),
        translator=Agent(client=client(translator_model or analyst_model), name="Translator",
                         instructions=TRANSLATOR_INSTRUCTIONS),
    )


# kept for the tests and for anyone calling it directly
def AgentFrameworkModel(name: str, base_url: str, api_key: str, analyst_model: str, narrator_model: str,  # noqa: N802
                        scout_model: str | None = None) -> AgentPairModel:
    return openai_compatible(name, base_url, api_key, analyst_model, narrator_model, scout_model)


TOKEN_SCOPES = ("https://ai.azure.com/.default", "https://cognitiveservices.azure.com/.default")


def _credential():
    """az login on a laptop, managed identity in Azure Container Apps.

    DefaultAzureCredential first tries environment variables and managed identity, which on a laptop
    can take seconds before it falls back to the Azure CLI. So outside Azure we go to the CLI directly.
    Set AZURE_CREDENTIAL=default to force DefaultAzureCredential anyway."""
    from azure.identity.aio import AzureCliCredential, DefaultAzureCredential

    in_azure = bool(os.getenv("IDENTITY_ENDPOINT") or os.getenv("MSI_ENDPOINT"))  # set by Container Apps
    if in_azure or os.getenv("AZURE_CREDENTIAL") == "default":
        return DefaultAzureCredential()
    return AzureCliCredential(process_timeout=30)


def foundry_code_agents(endpoint: str, analyst_model: str, narrator_model: str, credential=None,
                        scout_model: str | None = None, translator_model: str | None = None) -> AgentPairModel:
    """Agents defined in this code, running on model deployments in a Foundry project."""
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient

    cred = credential or _credential()

    def client(model: str):
        return FoundryChatClient(project_endpoint=endpoint, model=model, credential=cred)

    return AgentPairModel(
        name="foundry",
        analyst=Agent(client=client(analyst_model), name="Analyst", instructions=ANALYST_INSTRUCTIONS),
        narrator=Agent(client=client(narrator_model), name="Narrator", instructions=NARRATOR_INSTRUCTIONS),
        scout_agent=Agent(client=client(scout_model or analyst_model), name="Scout", instructions=SCOUT_INSTRUCTIONS),
        translator=Agent(client=client(translator_model or analyst_model), name="Translator",
                         instructions=TRANSLATOR_INSTRUCTIONS),
        credential=cred,
    )


def foundry_hosted_agents(endpoint: str, analyst: tuple[str, str], narrator: tuple[str, str], credential=None,
                          scout: tuple[str, str] | None = None, translator: tuple[str, str] | None = None) -> AgentPairModel:
    """Agents that live in Foundry Agent Service. Instructions, model and output schema come from Foundry."""
    from agent_framework.foundry import FoundryAgent

    cred = credential or _credential()
    return AgentPairModel(
        name="foundry-agents",
        analyst=FoundryAgent(project_endpoint=endpoint, agent_name=analyst[0], agent_version=analyst[1], credential=cred),
        narrator=FoundryAgent(project_endpoint=endpoint, agent_name=narrator[0], agent_version=narrator[1], credential=cred),
        scout_agent=(FoundryAgent(project_endpoint=endpoint, agent_name=scout[0], agent_version=scout[1], credential=cred)
                     if scout else None),
        translator=(FoundryAgent(project_endpoint=endpoint, agent_name=translator[0], agent_version=translator[1],
                                 credential=cred) if translator else None),
        pass_response_format=False,
        credential=cred,
    )


# ---------------------------------------------------------------- offline (no model)


class OfflineModel:
    """Deterministic stand-in: the first facts become the claims, the claims become the text."""

    name = "offline"

    async def draft(self, sheet: FactSheet, prompt: str) -> tuple[AnalystDraft, int | None]:
        facts = sheet.facts[:2]
        return AnalystDraft(claims=[Claim(text=f.text.rstrip(".") + ".", fact_ids=[f.fact_id]) for f in facts]), None

    async def scout(self, sheet: TacticalFactSheet, prompt: str) -> tuple[ScoutDraft, int | None]:
        """The facts with the playbook's consequence and coach response (no model)."""
        from .models import ScoutObservationDraft
        from .playbook import template_observations

        return ScoutDraft(observations=[
            ScoutObservationDraft(observation=o.observation, fact_ids=o.fact_ids, consequence=o.consequence,
                                  coach_action=o.coach_action or "", compare_to_cup=o.compare_to_cup, team=o.team or "")
            for o in template_observations(sheet)
        ]), None

    async def translate(self, lang: str, texts: list[str], prompt: str) -> tuple[TranslationDraft, int | None]:
        """A fixed "translation" for tests and demos without a model: the English text with the language tag,
        numbers as digits (as the Translator's instructions ask)."""
        from .checker import _words_to_digits

        return TranslationDraft(texts=[f"[{lang}] {_words_to_digits(t)}" for t in texts]), None

    async def narrate(self, sheet: FactSheet, claims: list[Claim], prompt: str) -> AsyncIterator[str]:
        text = f"{sheet.moment.headline}. " + " ".join(c.text for c in claims)
        for word in text.split(" "):
            yield word + " "


# ---------------------------------------------------------------- factory


def _need(var: str, why: str) -> str:
    v = os.getenv(var)
    if not v:
        raise RuntimeError(f"{why} needs {var}.")
    return v


def model_from_env(provider: str | None = None) -> ModelClient:
    provider = (provider or os.getenv("MODEL_PROVIDER") or ("github" if os.getenv("GITHUB_TOKEN") else "offline")).lower()
    if provider == "offline":
        return OfflineModel()
    if provider == "github":
        return openai_compatible(
            "github",
            base_url=os.getenv("GITHUB_MODELS_URL", GITHUB_MODELS_URL),
            api_key=_need("GITHUB_TOKEN", "MODEL_PROVIDER=github (a GitHub PAT with models:read)"),
            analyst_model=os.getenv("MODEL_ANALYST", "openai/gpt-4.1-mini"),
            narrator_model=os.getenv("MODEL_NARRATOR", "openai/gpt-4.1-nano"),
            scout_model=os.getenv("MODEL_SCOUT", "openai/gpt-4.1-mini"),
            translator_model=os.getenv("MODEL_TRANSLATOR", "openai/gpt-4.1-mini"),
        )
    if provider == "foundry":
        return foundry_code_agents(
            endpoint=_need("FOUNDRY_PROJECT_ENDPOINT", "MODEL_PROVIDER=foundry"),
            analyst_model=os.getenv("MODEL_ANALYST", "gpt-4.1-mini"),
            narrator_model=os.getenv("MODEL_NARRATOR", "gpt-4.1-mini"),
            scout_model=os.getenv("MODEL_SCOUT", "gpt-4.1-mini"),
            translator_model=os.getenv("MODEL_TRANSLATOR", "gpt-4.1-mini"),
        )
    if provider == "foundry-agents":
        why = "MODEL_PROVIDER=foundry-agents"
        return foundry_hosted_agents(
            endpoint=_need("FOUNDRY_PROJECT_ENDPOINT", why),
            analyst=(os.getenv("FOUNDRY_ANALYST_AGENT", "itg-analyst"), _need("FOUNDRY_ANALYST_AGENT_VERSION", why)),
            narrator=(os.getenv("FOUNDRY_NARRATOR_AGENT", "itg-narrator"), _need("FOUNDRY_NARRATOR_AGENT_VERSION", why)),
            # Optional: without a version the tactics cards use the template fallback, the rest keeps working.
            scout=((os.getenv("FOUNDRY_SCOUT_AGENT", "itg-scout"), os.environ["FOUNDRY_SCOUT_AGENT_VERSION"])
                   if os.getenv("FOUNDRY_SCOUT_AGENT_VERSION") else None),
            # Optional too: without it every card stays English (label "EN" in the UI).
            translator=((os.getenv("FOUNDRY_TRANSLATOR_AGENT", "itg-translator"), os.environ["FOUNDRY_TRANSLATOR_AGENT_VERSION"])
                        if os.getenv("FOUNDRY_TRANSLATOR_AGENT_VERSION") else None),
        )
    raise RuntimeError(f"Unknown MODEL_PROVIDER: {provider} (use github, foundry, foundry-agents or offline)")
