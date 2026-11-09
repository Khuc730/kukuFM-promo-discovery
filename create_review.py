
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "outputs" / "promos.csv"
OUTPUT_FILE = BASE_DIR / "outputs" / "human_review.csv"

review_columns = [
    "promo_id",
    "rank",
    "episode",
    "start_ts",
    "end_ts",
    "duration_sec",
    "heuristic_score",
    "hook_quality_1_to_5",
    "cliffhanger_quality_1_to_5",
    "standalone_clarity_1_to_5",
    "overall_rating_1_to_5",
    "decision",
    "reviewer_comments"
]

with open(INPUT_FILE, "r", encoding="utf-8-sig", newline="") as source:
    promos = list(csv.DictReader(source))

with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as output:
    writer = csv.DictWriter(output, fieldnames=review_columns)
    writer.writeheader()

    for promo in promos:
        writer.writerow({
            "promo_id": promo["promo_id"],
            "rank": promo["rank"],
            "episode": promo["episode"],
            "start_ts": promo["start_ts"],
            "end_ts": promo["end_ts"],
            "duration_sec": promo["duration_sec"],
            "heuristic_score": promo["heuristic_score"],
            "hook_quality_1_to_5": "",
            "cliffhanger_quality_1_to_5": "",
            "standalone_clarity_1_to_5": "",
            "overall_rating_1_to_5": "",
            "decision": "Pending",
            "reviewer_comments": ""
        })

print(f"Created human review sheet: {OUTPUT_FILE}")
print(f"Promos included: {len(promos)}")
