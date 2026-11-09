
"""LLM-based evaluation of promo candidates using Groq."""

import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq

from schemas import PromoJudgment


BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "outputs" / "judge_cache"

PROVIDER = os.getenv("LLM_PROVIDER", "groq").lower()
MODEL_NAME = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")


def extract_preceding_context(scene, candidate, context_duration=12):
    """Extract preceding screenplay context for interpretation."""

    context_start = max(0, candidate["start_sec"] - context_duration)
    context_end = candidate["start_sec"]

    context = []

    for element in scene["elements"]:
        if (
            element["start_sec"] >= context_start
            and element["end_sec"] <= context_end
        ):
            context.append({
                "start_ts": element["start_ts"],
                "end_ts": element["end_ts"],
                "speaker": element["speaker_or_label"],
                "kind": element["kind"],
                "text": element["text"]
            })

    context.sort(key=lambda item: item["start_ts"])
    return context


def build_judge_prompt(candidate, preceding_context=None):
    """Build a prompt for promotional quality evaluation."""

    candidate_content = []

    for element in candidate["elements"]:
        if (
            element["start_sec"] >= candidate["start_sec"]
            and element["end_sec"] <= candidate["end_sec"]
        ):
            candidate_content.append({
                "start_ts": element["start_ts"],
                "end_ts": element["end_ts"],
                "speaker": element["speaker_or_label"],
                "kind": element["kind"],
                "text": element["text"]
            })

    input_data = {
        "episode": candidate["episode"],
        "scene": candidate["scene_number"],
        "duration_sec": candidate["duration_sec"],
        "preceding_context": preceding_context or [],
        "candidate_content": candidate_content
    }

    schema = PromoJudgment.model_json_schema()

    return f"""
You are an experienced short-form microdrama promotional editor.

Evaluate the supplied 20–60 second candidate as an advertisement
intended to attract a viewer who has not watched the series.

Score each dimension from 1 to 10:

1. HOOK: Does the first three seconds create immediate curiosity,
   surprise, emotional engagement, or tension?
2. CLIFFHANGER: Does the ending leave an unresolved question,
   revelation, threat, or emotional development that encourages
   the viewer to continue watching?
3. STANDALONE: Can a new viewer understand the central situation
   without substantial knowledge of earlier episodes?
4. OVERALL: How effective is this segment as a promotional clip?

Be critical. Dramatic dialogue alone is not necessarily a good hook.
A dramatic statement is not necessarily a cliffhanger.

Rules:
- Evaluate only the candidate content.
- Preceding context is for understanding only.
- Any selected quote must be copied verbatim from candidate_content.
- The hook_quote must come from an element within the first
  3 seconds of the candidate.
- The cliffhanger must come from an element within the final
  5 seconds of the candidate.
- Do not select quotes from the middle of the candidate for either.
- If no suitable quote exists in the required time window,
  return an empty string for that field.
- Never invent dialogue, events, or timestamps.
- If there is no genuine hook or cliffhanger, reflect that in the score.
- Mention relevant editorial risks, such as missing context, violence,
  confusing character references, or weak narrative payoff.
- Keep explanations concise.
- Return one JSON object matching the supplied schema.
- Do not include Markdown fences or text outside the JSON object.
- Use an empty string if no suitable hook quote or cliffhanger quote exists.
- Use an empty list if there are no risk flags.

REQUIRED JSON SCHEMA:
{json.dumps(schema, ensure_ascii=False)}

INPUT:
{json.dumps(input_data, ensure_ascii=False)}
"""


def get_cache_path(candidate):
    """Create a stable cache filename for a candidate and model."""

    candidate_id = (
        f"{PROVIDER}_{MODEL_NAME}_"
        f"{candidate['episode']}_"
        f"{candidate['scene_number']}_"
        f"{candidate['start_sec']}_"
        f"{candidate['end_sec']}"
    )

    digest = hashlib.sha256(candidate_id.encode()).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def call_llm(prompt, schema=None):
    """Provider abstraction: call the configured LLM."""

    load_dotenv(BASE_DIR / ".env", override=True)

    if PROVIDER == "groq":
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            raise ValueError("GROQ_API_KEY not found in .env")

        client = Groq(api_key=api_key, timeout=120.0)

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert microdrama promotional editor. "
                        "Return only valid JSON matching the requested schema."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
            max_completion_tokens=1800,
            reasoning_effort="low"
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("Groq returned an empty response.")

        return content

    raise ValueError(
        f"Unsupported LLM_PROVIDER: {PROVIDER}. Currently supported: groq."
    )

def validate_quote_timing(judgment, candidate):
    """Ensure hook and cliffhanger quotes occur in the correct time windows."""

    first_three_seconds = candidate["start_sec"] + 3
    final_five_seconds = candidate["end_sec"] - 5

    for field, quote in [
        ("hook_quote", judgment.hook_quote),
        ("cliffhanger", judgment.cliffhanger)
    ]:
        if not quote:
            continue

        matching_elements = [
            element
            for element in candidate["elements"]
            if (
                element["start_sec"] >= candidate["start_sec"]
                and element["end_sec"] <= candidate["end_sec"]
                and quote in element["text"]
            )
        ]

        if not matching_elements:
            raise ValueError(
                f"{field} is not an exact quote from the candidate."
            )

        if field == "hook_quote":
            valid = any(
                element["start_sec"] < first_three_seconds
                for element in matching_elements
            )
        else:
            valid = any(
                element["end_sec"] >= final_five_seconds
                for element in matching_elements
            )

        if not valid:
            raise ValueError(
                f"{field} does not occur in its required time window."
            )

def judge_candidate(candidate, preceding_context=None, retries=2):
    """
    Evaluate one candidate using the configured LLM.

    Successful results are cached.
    Invalid responses and transient errors are retried.
    Returns PromoJudgment or None if evaluation fails.
    """

    load_dotenv(BASE_DIR / ".env", override=True)

    if PROVIDER == "groq" and not os.getenv("GROQ_API_KEY"):
        raise ValueError("GROQ_API_KEY not found in .env")

    cache_path = get_cache_path(candidate)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Reuse previously successful evaluations.
    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return PromoJudgment.model_validate(cached)
        except Exception:
            cache_path.unlink(missing_ok=True)

    prompt = build_judge_prompt(candidate, preceding_context)

    candidate_text = " ".join(
        element["text"]
        for element in candidate["elements"]
        if (
            element["start_sec"] >= candidate["start_sec"]
            and element["end_sec"] <= candidate["end_sec"]
        )
    )

    for attempt in range(retries + 1):
        try:
            response_text = call_llm(
                prompt,
                PromoJudgment.model_json_schema()
            )

            judgment = PromoJudgment.model_validate_json(response_text)

            # Verify selected quotes against actual candidate dialogue.
            validate_quote_timing(judgment, candidate)

            cache_path.write_text(
                judgment.model_dump_json(indent=2),
                encoding="utf-8"
            )

            return judgment

        except Exception as error:
            print(
                f"{PROVIDER.upper()} attempt {attempt + 1}/{retries + 1} "
                f"failed: {type(error).__name__}: {error}"
            )

            if attempt < retries:
                time.sleep(3 * (attempt + 1))

    return None
