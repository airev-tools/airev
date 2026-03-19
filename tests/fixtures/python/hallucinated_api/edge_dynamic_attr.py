import json
# json.loads is real but accessed dynamically — should NOT flag
loader = getattr(json, "loads")
