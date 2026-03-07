import json
import requests

URL = "https://api-v1.zyrooai.com/api/v1/math-classifier/interview/questions"

def download_questions(save_path="questions.json"):
    response = requests.get(URL, timeout=30)
    response.raise_for_status()  # throws error if request failed

    payload = response.json()

    # optional basic check
    if not payload.get("success", False):
        raise ValueError("API returned success=False")

    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Saved to {save_path}")
    print(f"Total questions: {payload['meta']['totalQuestions']}")

if __name__ == "__main__":
    download_questions()