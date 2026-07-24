"""Clean production entrypoint for CORQ Daily Predictions.

Architecture:
- THINQ = intelligence layer / brain
- CORQ = CORE output/ranking engine
- TOP7 = first 7 eligible picks from CORQ ranking

Run:
    python engine.py
"""

from corq.engine import main


if __name__ == "__main__":
    main()
