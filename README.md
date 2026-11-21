# Chess Review Bot

A game review tool I built from scratch: paste a PGN or pull your recent Chess.com games, and Stockfish reviews every move.

![Chess Review Bot](screenshot.png)

## Features

- **Full game review** with Stockfish: move labels (Best → Blunder), accuracy for both players, eval bar and an eval graph with mistake markers
- **Chess.com import**: enter a username, pick from your last games, review with one click
- **What-if scenarios**: drag any piece to try a different move, see how the engine rates it, and watch the engine's best line play out
- **Coach commentary**: plain-English notes such as "you left your bishop on c4 hanging" or "you missed mate", generated from the position and engine data (not from a language model, so it doesn't make things up)
- **Opening names** for common openings
- **Insights** from your last 50 games: win rate by colour, time control and opening, how you lose, rating trend
- **Shareable review links**: the whole review is packed into the URL
- Own board, pieces and theme (all drawn in code, nothing copied from other sites)

## How it works

| Part | Tech |
|---|---|
| Engine | [Stockfish](https://stockfishchess.org/) over UCI |
| Analysis + PGN handling | Python, [python-chess](https://github.com/niklasf/python-chess) |
| Server | FastAPI |
| Front end | Plain HTML/CSS/JS, [chess.js](https://github.com/jhlywa/chess.js) for move rules |

Move quality uses Lichess's published win-probability and accuracy formulas. The labels' thresholds are my own.

## Run it locally

1. Install Python 3.10+ and run `pip install -r requirements.txt`
2. Download Stockfish from <https://stockfishchess.org/download/> and extract it into this folder (or set the `STOCKFISH_PATH` environment variable to the exe)
3. Run `python server.py` (on Windows you can double-click `start.bat`). The app opens at <http://127.0.0.1:8000>

The command-line version also works: `python chess_review.py game.pgn --engine path/to/stockfish --depth 16`

## Notes

- Higher depth means a stronger but slower review (depth 14 is the default).
- This is a personal project and is not affiliated with Chess.com or Lichess. It reads games from Chess.com's public API.
- Stockfish is not included in this repository. It is free software under the GPL; see its website for the source and license.

## Roadmap

- Browser-only version (Stockfish in WebAssembly) so it can be hosted for free
- Brilliant / Great move labels
- Optional small-language-model "coach voice"
- Smoother piece animations
