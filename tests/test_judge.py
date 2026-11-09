
import json

from judge import judge_candidate, extract_preceding_context
from candidates import generate_windows
from schemas import PromoJudgment


# Load parsed screenplay data.
with open("outputs/parsed.json", "r", encoding="utf-8") as f:
    episodes = json.load(f)

# Select Episode 25.
episode = next(
    ep for ep in episodes
    if ep["episode"] == 25
)

candidates = []

# Generate candidates scene by scene.
for scene in episode["scenes"]:
    candidates.extend(
        generate_windows(scene, episode["episode"])
    )

if not candidates:
    raise RuntimeError("No candidates generated for Episode 25.")

# Select the candidate closest to the previously reviewed start time.
candidate = min(
    candidates,
    key=lambda c: abs(c["start_sec"] - 44.4)
)

# Find the corresponding scene.
scene = next(
    s for s in episode["scenes"]
    if s["scene_number"] == candidate["scene_number"]
)

context = extract_preceding_context(scene, candidate)

print("Testing candidate:")
print("Episode:", candidate["episode"])
print("Scene:", candidate["scene_number"])
print("Start:", candidate["start_sec"])
print("End:", candidate["end_sec"])
print("Duration:", candidate["duration_sec"])

judgment = judge_candidate(candidate, context)

if judgment:
    print("\nSUCCESS: Candidate evaluated.")
    print(judgment.model_dump_json(indent=2))
else:
    print("\nEvaluation failed. Check the error messages.")
