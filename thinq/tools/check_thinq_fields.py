import json
from pathlib import Path

path = Path("public/all_predictions_latest.json")
if not path.exists():
    path = Path("all_predictions_latest.json")

data = json.loads(path.read_text(encoding="utf-8"))
print("items:", len(data) if isinstance(data, list) else type(data))
if isinstance(data, list):
    total = len(data)
    available = sum(1 for x in data if isinstance(x, dict) and x.get("thinq_available") is True)
    failed = sum(1 for x in data if isinstance(x, dict) and x.get("thinq_available") is False)
    print("thinq_available_true:", available)
    print("thinq_available_false:", failed)
    for item in data[:5]:
        print(item.get("match"), "available=", item.get("thinq_available"), "conf=", item.get("thinq_confidence"), "elo=", item.get("thinq_elo_edge"), "err=", item.get("thinq_error"))
