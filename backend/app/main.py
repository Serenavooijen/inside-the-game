"""Inside the Game backend: one FastAPI process that replays a match and streams overlays."""
from fastapi import FastAPI

app = FastAPI(title="Inside the Game")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
