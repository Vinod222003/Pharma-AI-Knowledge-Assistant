import json
import os
from pathlib import Path
import requests

def main():
    base = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
    username = os.getenv("EVAL_USERNAME")
    password = os.getenv("EVAL_PASSWORD")
    if not username or not password:
        raise SystemExit("Set EVAL_USERNAME and EVAL_PASSWORD locally (do not commit or share them)")
    auth = requests.post(base + "/api/auth/login", json={"username": username, "password": password}, timeout=15)
    auth.raise_for_status()
    headers = {"Authorization": "Bearer " + auth.json()["access_token"]}
    cases = json.loads(Path("evaluation/questions.json").read_text(encoding="utf-8"))
    found = 0
    for case in cases:
        response = requests.post(base + "/api/ask", json={"question": case["question"]}, headers=headers, timeout=150)
        response.raise_for_status()
        result = response.json()
        sources = {x["filename"] for x in result["sources"]}
        ok = case["expected_source"] in sources
        found += ok
        print(f"{'PASS' if ok else 'FAIL'}: {case['question']} | sources={sorted(sources)}")
    print(f"Expected-source recall: {found}/{len(cases)} = {found/max(len(cases), 1):.1%}")
    print("Manual fact-grounding review is still required: source recall alone does not verify claims.")

if __name__ == "__main__":
    main()
