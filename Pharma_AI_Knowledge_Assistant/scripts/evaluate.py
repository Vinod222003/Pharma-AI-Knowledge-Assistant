import json
from pathlib import Path

def main():
    cases = json.loads(Path("evaluation/questions.json").read_text(encoding="utf-8"))
    print(f"Loaded {len(cases)} synthetic evaluation questions.")
    print("Smoke-test dataset only. Run the app, query each question, and have an expert score evidence relevance, groundedness and citation correctness.")
    for i, case in enumerate(cases, 1):
        print(f"{i}. {case['question']}")
if __name__ == "__main__":
    main()
