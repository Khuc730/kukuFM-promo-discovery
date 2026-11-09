
import json
import pandas as pd
import streamlit as st
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "outputs"

st.set_page_config(
    page_title="KukuFM | Promo Discovery",
    page_icon="🎬",
    layout="wide"
)


@st.cache_data
def load_data():
    with open(OUTPUT_DIR / "promos.json", encoding="utf-8") as f:
        promos = json.load(f)

    with open(OUTPUT_DIR / "parsed.json", encoding="utf-8") as f:
        episodes = json.load(f)

    return promos, episodes


promos, episodes = load_data()

episode_lookup = {
    episode["episode"]: episode
    for episode in episodes
}


def timestamp_to_seconds(timestamp):
    minutes, seconds = timestamp.split(":")
    return int(minutes) * 60 + float(seconds)


def get_promo_elements(promo):
    segment = promo["segments"][0]
    episode = episode_lookup.get(segment["episode"])

    if not episode:
        return []

    start = timestamp_to_seconds(segment["start_ts"])
    end = timestamp_to_seconds(segment["end_ts"])

    elements = []

    for scene in episode["scenes"]:
        for element in scene["elements"]:
            if (
                element["start_sec"] >= start
                and element["end_sec"] <= end
            ):
                elements.append(element)

    return sorted(elements, key=lambda item: item["start_sec"])


def get_llm_scores(promo):
    return promo.get("llm_scores") or {}


# Evaluation statistics
successful = [
    p for p in promos
    if p.get("evaluation_status") == "llm_evaluated"
]

failed = [
    p for p in promos
    if p.get("evaluation_status") == "llm_failed"
]

evaluated_scores = [
    get_llm_scores(p).get("overall_score")
    for p in successful
    if get_llm_scores(p).get("overall_score") is not None
]

average_llm_score = (
    sum(evaluated_scores) / len(evaluated_scores)
    if evaluated_scores else 0
)

average_heuristic_score = (
    sum(
        p["heuristic_scores"]["heuristic_score"]
        for p in promos
    ) / len(promos)
    if promos else 0
)


# --------------------------------------------------
# HEADER
# --------------------------------------------------

st.title("🎬 KukuFM Promo Discovery")

st.caption(
    "Discover, inspect, and evaluate promotional clips "
    "from 50 microdrama screenplays."
)

if successful:
    st.success(
        f"Groq LLM evaluation completed: {len(successful)} successful "
        f"evaluations and {len(failed)} failed evaluations."
    )
else:
    st.warning(
        "No successful LLM evaluations are available. "
        "Currently displaying heuristic screening results."
    )


# --------------------------------------------------
# OVERVIEW METRICS
# --------------------------------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Episodes", len(episodes))
col2.metric("Shortlisted promos", len(promos))

col3.metric(
    "Successful LLM evaluations",
    f"{len(successful)}/{len(promos)}"
)

col4.metric(
    "Average LLM score",
    f"{average_llm_score:.2f}/10"
    if evaluated_scores else "N/A"
)

st.divider()


# --------------------------------------------------
# FILTERS
# --------------------------------------------------

st.subheader("Explore shortlisted promos")

filter_col1, filter_col2, filter_col3 = st.columns(3)

episode_options = sorted(
    set(p["segments"][0]["episode"] for p in promos)
)

with filter_col1:
    selected_episode = st.selectbox(
        "Episode",
        ["All"] + episode_options
    )

with filter_col2:
    min_score = st.slider(
        "Minimum heuristic score",
        min_value=1.0,
        max_value=10.0,
        value=1.0,
        step=0.1
    )

with filter_col3:
    sort_order = st.selectbox(
        "Sort by",
        [
            "Rank",
            "Highest LLM score",
            "Highest heuristic score",
            "Longest duration"
        ]
    )


filtered = promos.copy()

if selected_episode != "All":
    filtered = [
        p for p in filtered
        if p["segments"][0]["episode"] == selected_episode
    ]

filtered = [
    p for p in filtered
    if p["heuristic_scores"]["heuristic_score"] >= min_score
]

if sort_order == "Highest LLM score":
    filtered.sort(
        key=lambda p: get_llm_scores(p).get("overall_score", 0),
        reverse=True
    )

elif sort_order == "Highest heuristic score":
    filtered.sort(
        key=lambda p: p["heuristic_scores"]["heuristic_score"],
        reverse=True
    )

elif sort_order == "Longest duration":
    filtered.sort(
        key=lambda p: p["total_duration_sec"],
        reverse=True
    )

else:
    filtered.sort(key=lambda p: p["rank"])


st.write(f"Showing **{len(filtered)}** promos")


# --------------------------------------------------
# PROMO CARDS
# --------------------------------------------------

for promo in filtered:

    segment = promo["segments"][0]

    heuristic = promo["heuristic_scores"]
    llm = get_llm_scores(promo)

    status = promo.get("evaluation_status", "unknown")

    llm_score = llm.get("overall_score")

    score_label = (
        f"LLM Score {llm_score:.1f}"
        if llm_score is not None
        else "LLM Not Evaluated"
    )

    with st.expander(
        f"#{promo['rank']} | Episode {segment['episode']} | "
        f"{promo['total_duration_sec']:.1f}s | {score_label}",
        expanded=(promo["rank"] == 1)
    ):

        left, right = st.columns([2, 1])

        # ------------------------------------------
        # LEFT: PROMO INFORMATION
        # ------------------------------------------

        with left:

            st.markdown("### Clip Information")

            st.write(f"**Episode:** {segment['episode']}")
            st.write(f"**Start:** {segment['start_ts']}")
            st.write(f"**End:** {segment['end_ts']}")
            st.write(
                f"**Duration:** {promo['total_duration_sec']:.1f}s"
            )

            st.markdown("### Screenplay Excerpt")

            elements = get_promo_elements(promo)

            if elements:
                for element in elements:
                    speaker = element.get("speaker_or_label", "")
                    text = element.get("text", "")

                    st.markdown(f"**{speaker}**: {text}")

            else:
                st.warning("No complete timed elements found.")

            # LLM evaluation details
            if llm:

                st.markdown("---")
                st.markdown("### AI-Generated Promo Analysis")

                if llm.get("hook_quote"):
                    st.markdown("**Hook Quote**")
                    st.info(llm["hook_quote"])

                if llm.get("cliffhanger"):
                    st.markdown("**Cliffhanger**")
                    st.info(llm["cliffhanger"])

                if llm.get("why_it_works"):
                    st.markdown("**Why It Works**")
                    st.write(llm["why_it_works"])

                if llm.get("standalone_context"):
                    st.markdown("**Standalone Context**")
                    st.write(llm["standalone_context"])

                if llm.get("confidence"):
                    st.markdown(
                        f"**Confidence:** {llm['confidence'].capitalize()}"
                    )

                risk_flags = llm.get("risk_flags", [])

                st.markdown("**Risk Flags**")

                if risk_flags:
                    for flag in risk_flags:
                        st.warning(flag)
                else:
                    st.success("No risk flags identified.")

        # ------------------------------------------
        # RIGHT: SCORES
        # ------------------------------------------

        with right:

            st.markdown("### Evaluation Scores")

            st.markdown("**LLM Scores**")

            if llm:

                st.metric(
                    "Overall",
                    f"{llm.get('overall_score', 0):.1f}/10"
                )

                score_col1, score_col2 = st.columns(2)

                score_col1.metric(
                    "Hook",
                    f"{llm.get('hook_score', 0)}/10"
                )

                score_col2.metric(
                    "Cliffhanger",
                    f"{llm.get('cliffhanger_score', 0)}/10"
                )

                st.metric(
                    "Standalone",
                    f"{llm.get('standalone_score', 0)}/10"
                )

            else:
                st.warning("LLM evaluation unavailable.")

            st.markdown("---")
            st.markdown("**Heuristic Scores**")

            st.metric(
                "Overall",
                f"{heuristic['heuristic_score']:.1f}/10"
            )

            st.metric(
                "Hook Indicators",
                f"{heuristic['hook_score']:.1f}/10"
            )

            st.metric(
                "Cliffhanger Indicators",
                f"{heuristic['cliffhanger_score']:.1f}/10"
            )

            st.metric(
                "Dialogue",
                f"{heuristic['dialogue_score']:.1f}/10"
            )

            st.caption(
                "Heuristic scores are preliminary indicators, "
                "not editorial judgments."
            )

            st.markdown("**Evaluation Status**")

            if status == "llm_evaluated":
                st.success("LLM Evaluated")

            elif status == "llm_failed":
                st.error("LLM Evaluation Failed")

            else:
                st.warning("Pending Evaluation")


# --------------------------------------------------
# EXPORT RESULTS
# --------------------------------------------------

st.divider()

st.subheader("Export Results")

json_data = json.dumps(
    promos,
    indent=2,
    ensure_ascii=False
)

csv_path = OUTPUT_DIR / "promos.csv"

col1, col2 = st.columns(2)

with col1:
    st.download_button(
        "Download promos.json",
        data=json_data,
        file_name="promos.json",
        mime="application/json"
    )

with col2:
    with open(csv_path, "rb") as f:
        st.download_button(
            "Download promos.csv",
            data=f,
            file_name="promos.csv",
            mime="text/csv"
        )

st.caption(
    "KukuFM Promo Discovery | "
    "Hybrid heuristic screening and Groq LLM evaluation"
)
