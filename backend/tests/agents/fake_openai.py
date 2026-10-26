"""
A tiny OpenAI-compatible chat-completions server for tests.

It lets us run the real Agent Framework code path (client, structured output,
streaming) without a token or network. Behaviour:
- with response_format: returns claims built from the first two facts in the prompt
  (or a wrong number when WRONG=True);
- with stream=True: streams the checked claims back word by word;
- SLOW_S > 0: waits before answering (to test the timeout).
"""

from __future__ import annotations

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"wrong": False, "slow_s": 0.0, "requests": []}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quiet
        pass

    def do_POST(self):  # noqa: N802
        try:
            self._post()
        except (BrokenPipeError, ConnectionResetError):
            pass  # the client gave up (timeout test)

    def _post(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        STATE["requests"].append(body)
        if STATE["slow_s"]:
            time.sleep(STATE["slow_s"])
        user = next(m for m in reversed(body["messages"]) if m["role"] == "user")
        text = user["content"] if isinstance(user["content"], str) else " ".join(p.get("text", "") for p in user["content"])

        schema = json.dumps(body.get("response_format") or {})
        if "observations" in schema:
            # The Scout: one observation per tactical fact, with a clean consequence
            # (or, with SCOUT_BAD, a consequence that adds a number and a coach action that adds a name).
            facts = re.findall(r"\[(T\d+)\] \((\w+), \w+\) (.+)", text)[:STATE.get("scout_n", 2)]
            obs = [{"observation": t, "fact_ids": [fid], "team": team, "compare_to_cup": "changed",
                    "consequence": "The opponent has to adjust the press.", "coach_action": "Keep the block compact."}
                   for fid, team, t in facts]
            if STATE.get("scout_bad") and obs:
                obs[0]["consequence"] = "That gives them 4 extra passes per minute."
                if len(obs) > 1:
                    obs[1]["coach_action"] = "Put Rasmussen on the 6."
            content = json.dumps({"observations": obs})
        elif body.get("response_format"):
            facts = re.findall(r"\[(F\d+)\] (.+)", text)[:2]
            claims = [{"text": t.rstrip(".") + ".", "fact_ids": [fid]} for fid, t in facts]
            if STATE["wrong"] and claims:
                claims[0]["text"] = re.sub(r"\d+(\.\d+)?", "9.99", claims[0]["text"], count=1)
            content = json.dumps({"claims": claims})
        else:
            lines = [l[2:] for l in text.splitlines() if l.startswith("- ")]
            content = " ".join(lines) or "No claims."

        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i, word in enumerate(content.split(" ")):
                chunk = {"id": "c1", "object": "chat.completion.chunk", "created": 0, "model": body["model"],
                         "choices": [{"index": 0, "delta": {"role": "assistant", "content": (" " if i else "") + word}, "finish_reason": None}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            end = {"id": "c1", "object": "chat.completion.chunk", "created": 0, "model": body["model"],
                   "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
            self.wfile.write(f"data: {json.dumps(end)}\n\ndata: [DONE]\n\n".encode())
            return

        resp = {"id": "c1", "object": "chat.completion", "created": 0, "model": body["model"],
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 40, "total_tokens": 160}}
        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start() -> tuple[str, ThreadingHTTPServer]:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", srv
