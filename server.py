"""
Run:  pip install fastapi uvicorn
      uvicorn server:app --port 8000
Then open http://127.0.0.1:8000

Keep server.py, chess_review.py and index.html in the same folder.
Stockfish: put the extracted folder next to these files, or set the
STOCKFISH_PATH environment variable to the exe (or its folder).
"""
import asyncio
import io
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import chess
import chess.engine
import chess.pgn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from chess_review import MATE_CP, resolve_engine, review

# Stockfish is launched as a subprocess; on Windows that needs the Proactor loop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

HERE = Path(__file__).parent
DEFAULT_ENGINE = str(HERE / "stockfish-windows-x86-64-universal")
app = FastAPI()


class ReviewRequest(BaseModel):
    pgn: str
    depth: int = 14


@app.get("/")
def index():
    return FileResponse(HERE / "index.html", headers={"Cache-Control": "no-store"})


@app.post("/api/review")
def api_review(req: ReviewRequest):
    game = chess.pgn.read_game(io.StringIO(req.pgn))
    if game is None or not list(game.mainline_moves()):
        raise HTTPException(400, "No moves found in that PGN.")
    try:
        path = resolve_engine(os.environ.get("STOCKFISH_PATH") or DEFAULT_ENGINE)
    except SystemExit as e:
        raise HTTPException(500, str(e))

    depth = max(8, min(req.depth, 22))
    try:
        with chess.engine.SimpleEngine.popen_uci(path) as engine:
            rows, acc, counts, evals = review(game, engine, chess.engine.Limit(depth=depth))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"{type(e).__name__}: {e!r}")

    avg = lambda a: round(sum(a) / len(a), 1) if a else 0
    h = game.headers
    return {
        "white": h.get("White", "?"),
        "black": h.get("Black", "?"),
        "result": h.get("Result", "*"),
        "start_fen": game.board().fen(),
        "start_cp": evals[0],
        "moves": [
            {"num": n, "san": san, "label": label, "best": best, "cp": ev}
            for n, san, label, best, ev in rows
        ],
        "accuracy": {"white": avg(acc[chess.WHITE]), "black": avg(acc[chess.BLACK])},
        "counts": {"white": counts[chess.WHITE], "black": counts[chess.BLACK]},
    }


# ---------- Chess.com game fetching ----------
CC_HEADERS = {"User-Agent": "chess-review-bot/1.0 (personal project)"}
DRAW_RESULTS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def cc_get(url):
    req = urllib.request.Request(url, headers=CC_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise HTTPException(404, "Chess.com user not found.")
        raise HTTPException(502, f"Chess.com returned error {e.code}.")
    except Exception as e:
        raise HTTPException(502, f"Could not reach Chess.com: {e}")


@app.get("/api/games")
def api_games(username: str, limit: int = 25):
    u = username.strip().lower()
    archives = cc_get(f"https://api.chess.com/pub/player/{u}/games/archives").get("archives", [])
    out = []
    for url in reversed(archives[-4:]):  # newest months first
        games = cc_get(url).get("games", [])
        for g in sorted(games, key=lambda x: x.get("end_time", 0), reverse=True):
            if g.get("rules") != "chess" or not g.get("pgn"):
                continue
            white, black = g["white"], g["black"]
            mine_white = white["username"].lower() == u
            me, opp = (white, black) if mine_white else (black, white)
            outcome = "W" if me["result"] == "win" else "D" if me["result"] in DRAW_RESULTS else "L"
            out.append({
                "pgn": g["pgn"],
                "opponent": opp["username"],
                "opp_rating": opp.get("rating", "?"),
                "color": "white" if mine_white else "black",
                "outcome": outcome,
                "time_class": g.get("time_class", ""),
                "my_result": me.get("result", ""),
                "rating": me.get("rating"),
                "date": datetime.fromtimestamp(g.get("end_time", 0), timezone.utc).strftime("%Y-%m-%d"),
            })
            if len(out) >= limit:
                return {"games": out}
    return {"games": out}


# ---------- single-position analysis (scenario mode) ----------
class AnalyseRequest(BaseModel):
    fen: str
    depth: int = 14


@app.post("/api/analyse")
def api_analyse(req: AnalyseRequest):
    try:
        board = chess.Board(req.fen)
    except ValueError:
        raise HTTPException(400, "Bad position.")
    if board.is_game_over():
        if board.is_checkmate():
            cp = -MATE_CP if board.turn == chess.WHITE else MATE_CP
        else:
            cp = 0
        return {"cp": cp, "best": None, "pv": []}
    try:
        path = resolve_engine(os.environ.get("STOCKFISH_PATH") or DEFAULT_ENGINE)
    except SystemExit as e:
        raise HTTPException(500, str(e))
    try:
        with chess.engine.SimpleEngine.popen_uci(path) as engine:
            info = engine.analyse(board, chess.engine.Limit(depth=max(8, min(req.depth, 20))))
    except Exception as e:
        raise HTTPException(500, f"{type(e).__name__}: {e!r}")
    cp = info["score"].white().score(mate_score=MATE_CP)
    sans, b = [], board.copy()
    for m in info.get("pv", [])[:8]:
        sans.append(b.san(m))
        b.push(m)
    return {"cp": cp, "best": sans[0] if sans else None, "pv": sans}


# ---------- start with:  python server.py  (or double-click start.bat) ----------
if __name__ == "__main__":
    import threading
    import webbrowser

    import uvicorn

    threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:8000")).start()
    uvicorn.run(app, host="127.0.0.1", port=8000)