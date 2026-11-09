
"""Run the promo pipeline with heuristic screening and Groq evaluation."""

import json
import csv
import time
from pathlib import Path

from candidates import (
    generate_windows,
    score_candidate,
    deduplicate_candidates
)

from judge import (
    judge_candidate,
    extract_preceding_context
)


BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = BASE_DIR / "outputs" / "parsed.json"
OUTPUT_DIR = BASE_DIR / "outputs"

OUTPUT_DIR.mkdir(exist_ok=True)


def seconds_to_timestamp(seconds):
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    return f"{minutes:02d}:{remaining:05.2f}"


def select_diverse_candidates(candidates, limit=50, max_per_episode=2):
    """Select high-scoring candidates while encouraging episode diversity."""

    ranked = sorted(
        candidates,
        key=lambda item: (
            item["scores"]["heuristic_score"],
            item["scores"]["hook_score"],
            item["scores"]["cliffhanger_score"],
            item["scores"]["dialogue_score"]
        ),
        reverse=True
    )

    selected = []
    episode_counts = {}

    # Pass 1: select the best candidate from each episode.
    for candidate in ranked:
        episode = candidate["episode"]

        if episode_counts.get(episode, 0) == 0:
            selected.append(candidate)
            episode_counts[episode] = 1

            if len(selected) == limit:
                return selected

    # Pass 2: fill remaining slots.
    selected_ids = {id(candidate) for candidate in selected}

    for candidate in ranked:
        if id(candidate) in selected_ids:
            continue

        episode = candidate["episode"]
        count = episode_counts.get(episode, 0)

        if count < max_per_episode:
            selected.append(candidate)
            episode_counts[episode] = count + 1
            selected_ids.add(id(candidate))

            if len(selected) == limit:
                break

    return selected


def evaluate_candidates(candidates):
    """Evaluate shortlisted candidates using the configured LLM."""

    results = []

    print("\nSTARTING LLM EVALUATION")
    print("------------------------------")

    for index, candidate in enumerate(candidates, start=1):

        scene = candidate["_scene"]

        context = extract_preceding_context(
            scene,
            candidate
        )

        print(
            f"\nEvaluating {index}/{len(candidates)} | "
            f"Episode {candidate['episode']} | "
            f"Scene {candidate['scene_number']} | "
            f"{candidate['duration_sec']} sec"
        )

        judgment = judge_candidate(
            candidate,
            preceding_context=context
        )

        if judgment:
            result = judgment.model_dump()

            print(
                f"LLM evaluation successful | "
                f"Overall score: {judgment.overall_score}/10"
            )

        else:
            result = None
            print("LLM evaluation failed for this candidate.")

        results.append({
            "candidate": candidate,
            "judgment": result
        })

        # Small pause between API requests.
        if index < len(candidates):
            time.sleep(1)

    return results


def rank_evaluated_candidates(results):
    """Rank successful LLM evaluations first, using heuristic scores as tie-breakers."""

    def ranking_key(item):
    judgment = item["judgment"]
    heuristic = item["candidate"]["scores"]

    if judgment is None:
        return (0, 0, 0, 0, heuristic["heuristic_score"])

    return (
        1,
        judgment["overall_score"],
        judgment["hook_score"],
        judgment["cliffhanger_score"],
        judgment["standalone_score"],
        heuristic["heuristic_score"]
    )




def create_promo(item, rank):
    """Convert an evaluated candidate into the final promo format."""

    candidate = item["candidate"]
    judgment = item["judgment"]

    promo = {
        "promo_id": (
            f"promo_ep{candidate['episode']}_"
            f"sc{candidate['scene_number']}_"
            f"{candidate['start_sec']}"
        ),
        "rank": rank,
        "segments": [{
            "episode": candidate["episode"],
            "start_ts": seconds_to_timestamp(
                candidate["start_sec"]
            ),
            "end_ts": seconds_to_timestamp(
                candidate["end_sec"]
            )
        }],
        "total_duration_sec": candidate["duration_sec"],
        "heuristic_scores": candidate["scores"],
        "evaluation_status": (
            "llm_evaluated" if judgment else "llm_failed"
        ),
        "llm_scores": None,
        "hook_quote": None,
        "cliffhanger": None,
        "why_it_works": None,
        "standalone_context": None,
        "confidence": None,
        "risk_flags": ["Human editorial review required"]
    }

    if judgment:
        promo["llm_scores"] = {
            "hook_score": judgment["hook_score"],
            "cliffhanger_score": judgment["cliffhanger_score"],
            "standalone_score": judgment["standalone_score"],
            "overall_score": judgment["overall_score"]
        }

        promo["hook_quote"] = judgment["hook_quote"]
        promo["cliffhanger"] = judgment["cliffhanger"]
        promo["why_it_works"] = judgment["why_it_works"]
        promo["standalone_context"] = judgment["standalone_context"]
        promo["confidence"] = judgment["confidence"]

        promo["risk_flags"].extend(
            judgment["risk_flags"]
        )

    else:
        promo["risk_flags"].append(
            "LLM evaluation failed; heuristic ranking only"
        )

    return promo


def write_json(promos):
    """Write final promo results to JSON."""

    with open(
        OUTPUT_DIR / "promos.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            promos,
            file,
            indent=2,
            ensure_ascii=False
        )


def write_csv(promos):
    """Write final promo results to CSV."""

    fieldnames = [
        "promo_id",
        "rank",
        "episode",
        "start_ts",
        "end_ts",
        "duration_sec",
        "heuristic_score",
        "hook_score",
        "cliffhanger_score",
        "standalone_score",
        "overall_score",
        "hook_quote",
        "cliffhanger",
        "confidence",
        "evaluation_status"
    ]

    with open(
        OUTPUT_DIR / "promos.csv",
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for promo in promos:
            segment = promo["segments"][0]
            llm = promo["llm_scores"] or {}

            writer.writerow({
                "promo_id": promo["promo_id"],
                "rank": promo["rank"],
                "episode": segment["episode"],
                "start_ts": segment["start_ts"],
                "end_ts": segment["end_ts"],
                "duration_sec": promo["total_duration_sec"],
                "heuristic_score": promo["heuristic_scores"]["heuristic_score"],
                "hook_score": llm.get("hook_score"),
                "cliffhanger_score": llm.get("cliffhanger_score"),
                "standalone_score": llm.get("standalone_score"),
                "overall_score": llm.get("overall_score"),
                "hook_quote": promo["hook_quote"],
                "cliffhanger": promo["cliffhanger"],
                "confidence": promo["confidence"],
                "evaluation_status": promo["evaluation_status"]
            })


def write_ranked_report(promos):
    """Write the top 10 LLM-ranked candidates."""

    with open(
        OUTPUT_DIR / "ranked_report.md",
        "w",
        encoding="utf-8"
    ) as file:

        file.write("# Promo Candidate Ranking Report\n\n")

        file.write("## Methodology\n\n")
        file.write(
            "Candidates were generated using deterministic "
            "20–60 second screenplay windows, filtered using "
            "rule-based heuristics, and evaluated using an LLM. "
            "Successfully evaluated candidates are ranked by "
            "LLM overall score, with heuristic score used as "
            "a tie-breaker. Human editorial review remains necessary.\n\n"
        )

        file.write("## Top 10 Candidates\n\n")

        for promo in promos[:10]:
            segment = promo["segments"][0]
            llm = promo["llm_scores"]

            file.write(
                f"### Rank {promo['rank']} — "
                f"Episode {segment['episode']}\n\n"
            )

            file.write(
                f"- **Time:** {segment['start_ts']}–"
                f"{segment['end_ts']}\n"
            )

            file.write(
                f"- **Duration:** "
                f"{promo['total_duration_sec']} seconds\n"
            )

            file.write(
                f"- **Heuristic score:** "
                f"{promo['heuristic_scores']['heuristic_score']}\n"
            )

            if llm:
                file.write(
                    f"- **LLM overall score:** "
                    f"{llm['overall_score']}/10\n"
                )

                file.write(
                    f"- **Hook:** {llm['hook_score']}/10\n"
                )

                file.write(
                    f"- **Cliffhanger:** "
                    f"{llm['cliffhanger_score']}/10\n"
                )

                file.write(
                    f"- **Standalone:** "
                    f"{llm['standalone_score']}/10\n"
                )

                file.write(
                    f"- **Hook quote:** {promo['hook_quote']}\n"
                )

                file.write(
                    f"- **Cliffhanger:** {promo['cliffhanger']}\n"
                )

                file.write(
                    f"- **Why it works:** {promo['why_it_works']}\n"
                )

                file.write(
                    f"- **Standalone context:** "
                    f"{promo['standalone_context']}\n"
                )

                file.write(
                    f"- **Confidence:** {promo['confidence']}\n"
                )

            else:
                file.write(
                    "- **Evaluation:** LLM evaluation failed\n"
                )

            file.write(
                f"- **Risk flags:** "
                f"{', '.join(promo['risk_flags'])}\n\n"
            )


def write_failure_analysis(
    episodes,
    total_scenes,
    scenes_without_candidates,
    all_candidates,
    unique_candidates,
    selected,
    promos
):
    """Write dataset statistics, evaluation results and limitations."""

    successful = sum(
        promo["evaluation_status"] == "llm_evaluated"
        for promo in promos
    )

    failed = len(promos) - successful

    with open(
        OUTPUT_DIR / "failure_analysis.md",
        "w",
        encoding="utf-8"
    ) as file:

        file.write("# Failure Analysis and Limitations\n\n")

        file.write("## Dataset processing\n\n")
        file.write(f"- Episodes processed: {len(episodes)}\n")
        file.write(f"- Scenes processed: {total_scenes}\n")
        file.write(
            f"- Scenes without valid-duration candidates: "
            f"{scenes_without_candidates}\n"
        )
        file.write(f"- Raw candidates: {len(all_candidates)}\n")
        file.write(
            f"- Candidates after temporal deduplication: "
            f"{len(unique_candidates)}\n"
        )
        file.write(f"- Candidates shortlisted: {len(selected)}\n")

        file.write("\n## LLM evaluation\n\n")
        file.write(f"- Successfully evaluated: {successful}\n")
        file.write(f"- Failed evaluations: {failed}\n")
        file.write("- Provider: Groq\n")
        file.write("- Model: openai/gpt-oss-20b\n")

        file.write("\n## Known limitations\n\n")
        file.write(
            "1. Heuristic screening may miss strong narrative "
            "moments or retain weak candidates.\n"
        )
        file.write(
            "2. LLM judgments are subjective and may vary between "
            "evaluations.\n"
        )
        file.write(
            "3. Temporal deduplication does not guarantee "
            "story-level diversity.\n"
        )
        file.write(
            "4. Candidate boundaries align with timed-element "
            "boundaries, but editorial continuity requires human review.\n"
        )
        file.write(
            "5. Multi-segment promos have not been implemented.\n"
        )
        file.write(
            "6. Quote verification checks source-text presence and "
            "timing windows, but does not replace manual verification.\n"
        )

        file.write("\n## Recommended improvements\n\n")
        file.write(
            "- Review the highest-ranked promos manually.\n"
            "- Compare LLM judgments with human ratings.\n"
            "- Inspect low-confidence and failed evaluations.\n"
            "- Review standalone clarity and narrative continuity.\n"
            "- Explore multi-segment promo combinations.\n"
        )


def run_pipeline():

    with open(
        INPUT_FILE,
        "r",
        encoding="utf-8"
    ) as file:
        episodes = json.load(file)

    all_candidates = []
    total_scenes = 0
    scenes_without_candidates = 0

    print("\nGENERATING CANDIDATES")
    print("------------------------------")

    # Stage 1: Generate and score candidates.
    for episode in episodes:
        for scene in episode["scenes"]:
            total_scenes += 1

            candidates = generate_windows(
                scene,
                episode["episode"]
            )

            if not candidates:
                scenes_without_candidates += 1

            for candidate in candidates:
                candidate["scores"] = score_candidate(candidate)

                # Retain the scene for preceding-context extraction.
                candidate["_scene"] = scene

                all_candidates.append(candidate)

    # Stage 2: Temporal deduplication.
    unique_candidates = deduplicate_candidates(all_candidates)

    # Stage 3: Diverse heuristic shortlist.
    selected = select_diverse_candidates(
        unique_candidates,
        limit=50,
        max_per_episode=2
    )

    print("\nCANDIDATE SCREENING COMPLETED")
    print("------------------------------")
    print("Episodes:", len(episodes))
    print("Scenes:", total_scenes)
    print("Raw candidates:", len(all_candidates))
    print("After deduplication:", len(unique_candidates))
    print("Shortlisted:", len(selected))

    # Stage 4: LLM evaluation.
    results = evaluate_candidates(selected)

    # Stage 5: Final ranking.
    ranked_results = rank_evaluated_candidates(results)

    promos = [
        create_promo(item, rank)
        for rank, item in enumerate(ranked_results, start=1)
    ]

    # Stage 6: Generate deliverables.
    write_json(promos)
    write_csv(promos)
    write_ranked_report(promos)

    write_failure_analysis(
        episodes,
        total_scenes,
        scenes_without_candidates,
        all_candidates,
        unique_candidates,
        selected,
        promos
    )

    successful = sum(
        promo["evaluation_status"] == "llm_evaluated"
        for promo in promos
    )

    failed = len(promos) - successful

    print("\nPIPELINE COMPLETED")
    print("------------------------------")
    print("Episodes:", len(episodes))
    print("Scenes:", total_scenes)
    print("Raw candidates:", len(all_candidates))
    print("After deduplication:", len(unique_candidates))
    print("Shortlisted:", len(selected))
    print("LLM evaluations successful:", successful)
    print("LLM evaluations failed:", failed)

    print("\nGenerated files:")
    print("outputs/promos.json")
    print("outputs/promos.csv")
    print("outputs/ranked_report.md")
    print("outputs/failure_analysis.md")


if __name__ == "__main__":
    run_pipeline()
