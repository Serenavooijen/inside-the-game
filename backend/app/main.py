"""Inside the Game backend: one FastAPI process that replays a match and streams it.

Endpoints and SSE messages follow frontend/README.md; the frontend switches from its
mock to this backend with NEXT_PUBLIC_API_URL=http://localhost:8000.
"""
import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.agents.llm import model_from_env
from app.bus import EventBus
from app.contracts import LoadRequest, SeekRequest, SpeedRequest
from app.fixture import MATCH_ID, SUMMARY, GeneratorSource
from app.simulator import Simulator
from app.smart_lane import SmartLane

CORS_ORIGINS = os.environ.get("ITG_CORS_ORIGINS", "http://localhost:3000").split(",")

bus = EventBus()
smart_lane = SmartLane(model_from_env())    # MODEL_PROVIDER: offline (default), github, foundry, foundry-agents
simulator = Simulator(bus, {MATCH_ID: GeneratorSource}, smart_lane)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await smart_lane.warmup()
    task = asyncio.create_task(simulator.run())
    yield
    task.cancel()
    smart_lane.cancel_all()


app = FastAPI(title="Inside the Game", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


def _require_loaded() -> None:
    if not simulator.loaded:
        raise HTTPException(409, "No match loaded: POST /match/load first")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/matches")
def matches() -> list[dict]:
    return [SUMMARY.to_json()]


@app.post("/match/load")
async def load(body: LoadRequest) -> dict[str, bool]:
    try:
        await simulator.load(body.match_id, body.mode)
    except KeyError:
        raise HTTPException(404, f"Unknown match: {body.match_id}")
    return {"ok": True}


@app.post("/play")
def play() -> dict[str, bool]:
    _require_loaded()
    simulator.play()
    return {"ok": True}


@app.post("/pause")
def pause() -> dict[str, bool]:
    _require_loaded()
    simulator.pause()
    return {"ok": True}


@app.post("/speed")
def speed(body: SpeedRequest) -> dict[str, bool]:
    _require_loaded()
    simulator.set_speed(body.factor)
    return {"ok": True}


@app.post("/seek")
def seek(body: SeekRequest) -> dict[str, bool]:
    _require_loaded()
    simulator.seek(body.t)
    return {"ok": True}


@app.get("/state")
def state() -> dict:
    _require_loaded()
    return simulator.state().to_json()


@app.get("/stream")
async def stream(request: Request) -> EventSourceResponse:
    queue = bus.subscribe()

    async def messages():
        try:
            if simulator.loaded:
                yield {"event": "state", "data": json.dumps(simulator.state().to_json())}
            while not await request.is_disconnected():
                try:
                    name, data = await asyncio.wait_for(queue.get(), timeout=1.0)
                except TimeoutError:
                    continue
                yield {"event": name, "data": json.dumps(data)}
        finally:
            bus.unsubscribe(queue)

    return EventSourceResponse(messages(), ping=15)
