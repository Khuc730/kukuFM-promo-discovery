"""Rule-based generation of potential promo candidates."""

def flatten_episode(episode):
    """
    Convert nested episode data into a chronological list
    of timed elements.
    """
    flattened = []

    for scene in episode["scenes"]:
        for element in scene["elements"]:

            item = element.copy()

            item["episode"] = episode["episode"]
            item["scene_number"] = scene["scene_number"]
            item["scene_heading"] = scene["heading"]

            flattened.append(item)

    flattened.sort(
        key=lambda item: (item["start_sec"], item["end_sec"])
    )

    return flattened


def generate_windows(scene, episode_number):
    """
    Generate 20–60 second candidate windows.

    Every timed element overlapping a candidate must be completely
    contained within it. Windows that cut through dialogue or action
    elements are rejected.
    """
    MIN_DURATION = 20
    MAX_DURATION = 60

    elements = scene["elements"]
    boundaries = set()

    for element in elements:
        boundaries.add(element["start_sec"])
        boundaries.add(element["end_sec"])

    boundaries = sorted(boundaries)
    candidates = []

    for start_index, start_time in enumerate(boundaries):
        for end_time in boundaries[start_index + 1:]:

            duration = end_time - start_time

            if not MIN_DURATION <= duration <= MAX_DURATION:
                continue

            overlapping_elements = [
                element for element in elements
                if (
                    element["start_sec"] < end_time
                    and element["end_sec"] > start_time
                )
            ]

            # Reject windows that cut through any timed element.
            has_cut_element = any(
                element["start_sec"] < start_time
                or element["end_sec"] > end_time
                for element in overlapping_elements
            )

            if has_cut_element or not overlapping_elements:
                continue

            candidates.append({
                "episode": episode_number,
                "scene_number": scene["scene_number"],
                "scene_heading": scene["heading"],
                "start_sec": start_time,
                "end_sec": end_time,
                "duration_sec": round(duration, 2),
                "elements": overlapping_elements
            })

    return candidates


def get_candidate_text(elements):
    """Combine the text of all elements into one string."""
    return " ".join(
        element["text"] for element in elements
    )



def get_elements_in_range(elements, start, end):
    """Return only elements completely contained in the interval."""
    return [
        element for element in elements
        if (
            element["start_sec"] >= start
            and element["end_sec"] <= end
        )
    ]



def score_candidate(candidate):
    """
    Assign a preliminary heuristic score to a candidate.
    This is a screening score, not an LLM quality judgment.
    """

    elements = candidate["elements"]

    start = candidate["start_sec"]
    end = candidate["end_sec"]

    # Examine the opening 3 seconds.
    opening_elements = get_elements_in_range(
        elements, start, min(start + 3, end)
    )

    # Examine the final 5 seconds.
    ending_elements = get_elements_in_range(
        elements, max(start, end - 5), end
    )

    opening_text = get_candidate_text(opening_elements).lower()
    ending_text = get_candidate_text(ending_elements).lower()

    full_text = get_candidate_text(elements)

    dialogue_count = sum(
        1 for element in elements
        if element["kind"] == "dialogue"
    )

    action_count = sum(
        1 for element in elements
        if element["kind"] == "action"
    )

    # Preliminary attention-grabbing language.
    hook_words = [
        "what", "why", "how", "never", "stop",
        "please", "help", "betray", "love", "kill"
    ]

    # Preliminary suspense/revelation language.
    cliffhanger_words = [
        "but", "unless", "secret", "truth", "wait",
        "who", "why", "what", "never", "promise"
    ]

    hook_score = sum(
        1 for word in hook_words
        if word in opening_text
    )

    cliffhanger_score = sum(
        1 for word in cliffhanger_words
        if word in ending_text
    )

    # Normalize the signals to a 0–10 range.
    hook_score = min(hook_score * 2, 10)
    cliffhanger_score = min(cliffhanger_score * 2, 10)

    dialogue_score = min(dialogue_count / 5, 1) * 10

    activity_score = min(
        (dialogue_count + action_count) / 10, 1
    ) * 10

    overall_score = (
        0.30 * hook_score
        + 0.30 * cliffhanger_score
        + 0.25 * dialogue_score
        + 0.15 * activity_score
    )

    return {
        "hook_score": round(hook_score, 2),
        "cliffhanger_score": round(cliffhanger_score, 2),
        "dialogue_score": round(dialogue_score, 2),
        "activity_score": round(activity_score, 2),
        "heuristic_score": round(overall_score, 2)
    }

def calculate_temporal_iou(candidate_a, candidate_b):
    """Calculate overlap between two time intervals."""

    intersection = max(
        0,
        min(candidate_a["end_sec"], candidate_b["end_sec"])
        - max(candidate_a["start_sec"], candidate_b["start_sec"])
    )

    duration_a = candidate_a["end_sec"] - candidate_a["start_sec"]
    duration_b = candidate_b["end_sec"] - candidate_b["start_sec"]

    union = duration_a + duration_b - intersection

    return intersection / union if union > 0 else 0



def deduplicate_candidates(candidates, overlap_threshold=0.85):
    """
    Remove near-duplicates using temporal IoU and containment.
    Only candidates from the same episode and scene are compared.
    """
    ranked = sorted(
        candidates,
        key=lambda item: (
            item["scores"]["heuristic_score"],
            item["duration_sec"]
        ),
        reverse=True
    )

    selected = []

    for candidate in ranked:
        is_duplicate = False

        for chosen in selected:
            same_scene = (
                candidate["episode"] == chosen["episode"]
                and candidate["scene_number"] == chosen["scene_number"]
            )

            if not same_scene:
                continue

            iou = calculate_temporal_iou(candidate, chosen)

            intersection = max(
                0,
                min(candidate["end_sec"], chosen["end_sec"])
                - max(candidate["start_sec"], chosen["start_sec"])
            )

            shorter_duration = min(
                candidate["duration_sec"],
                chosen["duration_sec"]
            )

            containment = (
                intersection / shorter_duration
                if shorter_duration > 0 else 0
            )

            if (
                iou >= overlap_threshold
                or containment >= 0.95
            ):
                is_duplicate = True
                break

        if not is_duplicate:
            selected.append(candidate)

    return selected


if __name__ == "__main__":
    import json

    # Load all parsed episodes.
    with open("outputs/parsed.json", "r", encoding="utf-8") as file:
        episodes = json.load(file)

    all_candidates = []

    total_scenes = 0
    scenes_without_candidates = 0

    # Process every episode and every scene.
    for episode in episodes:

        for scene in episode["scenes"]:

            total_scenes += 1

            candidates = generate_windows(
                scene,
                episode["episode"]
            )

            if not candidates:
                scenes_without_candidates += 1

            # Calculate heuristic scores.
            for candidate in candidates:
                candidate["scores"] = score_candidate(candidate)

            all_candidates.extend(candidates)

    print("Dataset processing complete.")
    print("Episodes processed:", len(episodes))
    print("Scenes processed:", total_scenes)
    print("Scenes without candidates:", scenes_without_candidates)
    print("Total candidates generated:", len(all_candidates))

    # Remove near-duplicate candidates.
    unique_candidates = deduplicate_candidates(all_candidates)

    print("\nAfter deduplication:")
    print("Unique candidates:", len(unique_candidates))
    print(
        "Candidates removed:",
        len(all_candidates) - len(unique_candidates)
    )

    # Display the top 20 candidates.
    print("\nTop 20 unique candidates:\n")

    for index, candidate in enumerate(unique_candidates[:20], start=1):

        print(
            f"{index}. Episode {candidate['episode']} | "
            f"Scene {candidate['scene_number']} | "
            f"{candidate['start_sec']:.2f}s - "
            f"{candidate['end_sec']:.2f}s | "
            f"Duration: {candidate['duration_sec']}s | "
            f"Score: {candidate['scores']['heuristic_score']}"
        )

    # Inspect the actual screenplay content of the top 5 candidates.
    print("\n\nTOP 5 CANDIDATE CONTENTS")

    for index, candidate in enumerate(unique_candidates[:5], start=1):

        print("\n" + "=" * 70)
        print(f"CANDIDATE {index}")
        print(
            f"Episode: {candidate['episode']} | "
            f"Scene: {candidate['scene_number']}"
        )
        print(
            f"Time: {candidate['start_sec']}s - "
            f"{candidate['end_sec']}s"
        )

        for element in candidate["elements"]:
            print(
                f"[{element['start_ts']} - {element['end_ts']}] "
                f"{element['speaker_or_label']}: "
                f"{element['text']}"
            )