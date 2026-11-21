#!/usr/bin/env python3
"""
Chess game review bot.

Setup:
    pip install python-chess
    Install Stockfish (https://stockfishchess.org/download/) and note its path.

Usage:
    python chess_review.py game.pgn --engine /path/to/stockfish --depth 16
    (If "stockfish" is on your PATH, --engine can be omitted.)
"""
import argparse
import math
import shutil
import sys

import chess
import chess.engine
import chess.pgn

MATE_CP = 10000  # centipawn value used for forced mates


def win_pct(cp: float) -> float:
    """Lichess's centipawn -> win% curve (from the mover's point of view)."""
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def move_accuracy(before: float, after: float) -> float:
    """Lichess's per-move accuracy formula, based on win% lost."""
    diff = max(0.0, before - after)
    acc = 103.1668 * math.exp(-0.04354 * diff) - 3.1669
    return max(0.0, min(100.0, acc + 1))  # +1 uncertainty bonus, as Lichess does


def classify(loss: float, is_best: bool) -> str:
    """Label a move by win% lost."""
    if is_best or loss <= 0.5:
        return "Best"
    if loss <= 2:
        return "Excellent"
    if loss <= 5:
        return "Good"
    if loss <= 10:
        return "Inaccuracy"
    if loss <= 20:
        return "Mistake"
    return "Blunder"


def eval_position(engine, board, limit):
    """Return (white-perspective centipawns, best move or None)."""
    if board.is_checkmate():
        # Side to move has been mated.
        return (-MATE_CP if board.turn == chess.WHITE else MATE_CP), None
    if board.is_game_over():
        return 0, None  # stalemate, insufficient material, etc.
    info = engine.analyse(board, limit)
    cp = info["score"].white().score(mate_score=MATE_CP)
    best = info["pv"][0] if info.get("pv") else None
    return cp, best


def review(game, engine, limit):
    board = game.board()
    moves = list(game.mainline_moves())

    # Analyse every position once (n+1 positions for n moves).
    evals, bests = [], []
    scratch = game.board()
    for i in range(len(moves) + 1):
        cp, best = eval_position(engine, scratch, limit)
        evals.append(cp)
        bests.append(best)
        if i < len(moves):
            scratch.push(moves[i])
        print(f"\rAnalysing... {i + 1}/{len(moves) + 1}", end="", file=sys.stderr)
    print(file=sys.stderr)

    rows = []
    acc = {chess.WHITE: [], chess.BLACK: []}
    counts = {chess.WHITE: {}, chess.BLACK: {}}

    for i, move in enumerate(moves):
        color = board.turn
        sign = 1 if color == chess.WHITE else -1
        before = win_pct(sign * evals[i])
        after = win_pct(sign * evals[i + 1])
        loss = max(0.0, before - after)
        is_best = bests[i] == move
        label = classify(loss, is_best)

        san = board.san(move)
        best_san = board.san(bests[i]) if bests[i] else None
        number = f"{board.fullmove_number}{'.' if color == chess.WHITE else '...'}"

        acc[color].append(move_accuracy(before, after))
        counts[color][label] = counts[color].get(label, 0) + 1
        rows.append((number, san, label, best_san, evals[i + 1]))
        board.push(move)

    return rows, acc, counts, evals


def fmt_eval(cp):
    if abs(cp) >= MATE_CP - 100:
        n = MATE_CP - abs(cp)
        return f"{'+' if cp > 0 else '-'}M{n}"
    return f"{cp / 100:+.2f}"


def resolve_engine(path):
    """Find a runnable Stockfish exe, or exit with a clear message."""
    import glob
    import os

    if not path:
        sys.exit("No engine given. Pass --engine \"C:\\path\\to\\stockfish.exe\"")
    path = path.strip().strip('"').strip("'")

    if os.path.isdir(path):
        found = glob.glob(os.path.join(path, "**", "stockfish*.exe"), recursive=True)
        if found:
            print(f"Found engine: {found[0]}", file=sys.stderr)
            return found[0]
        sys.exit(f"That's a folder and I found no stockfish*.exe inside it:\n  {path}")

    if not os.path.isfile(path):
        if os.path.isfile(path + ".exe"):
            return path + ".exe"
        sys.exit(f"No file exists at this path:\n  {path}\n"
                 "Check the spelling, make sure the zip is extracted, and that it ends in .exe")
    return path


def main():
    p = argparse.ArgumentParser(description="Review a chess game with Stockfish.")
    p.add_argument("pgn", help="Path to a PGN file (first game is reviewed)")
    p.add_argument("--engine", default=shutil.which("stockfish"), help="Path to Stockfish")
    p.add_argument("--depth", type=int, default=16, help="Search depth (default 16)")
    args = p.parse_args()

    args.engine = resolve_engine(args.engine)

    with open(args.pgn, encoding="utf-8") as f:
        game = chess.pgn.read_game(f)
    if game is None:
        sys.exit("No game found in PGN.")

    h = game.headers
    print(f"{h.get('White', '?')} vs {h.get('Black', '?')}  |  {h.get('Result', '*')}\n")

    with chess.engine.SimpleEngine.popen_uci(args.engine) as engine:
        rows, acc, counts, _ = review(game, engine, chess.engine.Limit(depth=args.depth))

    print(f"{'Move':<8}{'Played':<10}{'Verdict':<12}{'Eval':<8}Better move")
    print("-" * 52)
    for number, san, label, best_san, ev in rows:
        better = best_san if label not in ("Best", "Excellent", "Good") else ""
        print(f"{number:<8}{san:<10}{label:<12}{fmt_eval(ev):<8}{better}")

    print("\nSummary")
    print("-" * 52)
    for color, name in ((chess.WHITE, "White"), (chess.BLACK, "Black")):
        a = acc[color]
        avg = sum(a) / len(a) if a else 0
        parts = ", ".join(f"{k}: {v}" for k, v in sorted(counts[color].items()))
        print(f"{name}: accuracy {avg:.1f}%  ({parts})")


if __name__ == "__main__":
    main()
