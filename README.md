# KukuFM – Find the Promos (Ads)

## 1. Problem Statement

The objective is to identify compelling 20–60 second promotional segments from 50 microdrama screenplay files.

A good promo should:
- Capture attention within the first 3 seconds.
- End with suspense, curiosity, or emotional tension.
- Be understandable to a new viewer.
- Preserve original screenplay dialogue and timestamps.

## 2. Solution Overview

The solution uses a hybrid pipeline combining deterministic Python processing, rule-based candidate generation, heuristic ranking, and LLM-based evaluation.

### Pipeline

1. Parse screenplay text files.
2. Extract scenes and timed elements.
3. Generate candidate windows of 20–60 seconds.
4. Calculate preliminary heuristic scores.
5. Remove near-duplicate candidates using temporal Intersection over Union (IoU).
6. Select a diverse shortlist of up to 50 candidates.
7. Prepare candidate content and preceding context for LLM evaluation.
8. Evaluate candidates using Groq.
9. Validate structured judgments using Pydantic and verify selected quotes against screenplay content and timing.
10. Rank evaluated candidates and generate reports.

**Implementation status:** The deterministic and heuristic pipeline is operational. Groq integration using `openai/gpt-oss-20b` is working. Of the 50 shortlisted candidates, 48 were successfully evaluated and 2 failed quote validation after retries.

## 3. Project Structure

```text
code/
├── data/                       # 50 screenplay files
├── outputs/
│   ├── parsed.json
│   ├── promos.json
│   ├── promos.csv
│   ├── ranked_report.md
│   ├── failure_analysis.md
│   ├── human_review.csv
│   └── judge_cache/            # Cached LLM judgments
├── tests/
│   ├── test_parse.py
│   ├── test_judge.py
│   └── test_groq.py
├── parse.py                    # Deterministic screenplay parser
├── candidates.py               # Candidate generation and scoring
├── schemas.py                  # Pydantic judgment schema
├── judge.py                    # LLM judge and prompt construction
├── run.py                      # Main pipeline
├── create_review.py             # Human review template generator
├── requirements.txt
├── .env                        # API keys and configuration
├── .gitignore
└── README.md
```

## 4. Technology Stack

- Python
- Groq API
- `openai/gpt-oss-20b`
- Groq Python SDK
- Pydantic
- python-dotenv
- JSON and CSV

## 5. Candidate Generation

The candidate generator creates windows using timed screenplay element boundaries.

Constraints:
- Minimum duration: 20 seconds.
- Maximum duration: 60 seconds.
- Candidate windows are generated within individual scenes.
- Candidate boundaries must align with complete timed screenplay elements.

Preliminary heuristic factors:
- Opening hook keywords.
- Ending cliffhanger keywords.
- Dialogue density.
- Activity density.

Near-duplicate candidates are removed using temporal Intersection over Union (IoU), with a threshold of 0.85, along with a containment-based check.

A diversity selection step prioritizes the highest-scoring candidate from each episode before filling the remaining shortlist, allowing at most two candidates per episode.

## 6. LLM Evaluation Design

The Groq judge evaluates each shortlisted candidate on:

- Hook score (1–10).
- Cliffhanger score (1–10).
- Standalone score (1–10).
- Overall score (1–10).
- Hook quote.
- Cliffhanger.
- Explanation of why the promo works.
- Standalone context.
- Confidence.
- Risk flags.

Preceding screenplay context is supplied separately from candidate content to help the model interpret the scene without treating preceding dialogue as part of the promo.

Pydantic validates the expected structured response.

Additional validation checks:
- Selected quotes must match the candidate screenplay text.
- Hook quotes must occur within the first 3 seconds.
- Cliffhanger quotes must occur within the final 5 seconds.

Successful evaluations are cached to avoid repeated API calls. Failed evaluations are retried, and the pipeline continues if an individual candidate cannot be evaluated.

## 7. Dataset Results

| Metric | Result |
|---|---:|
| Episodes processed | 50 |
| Scenes processed | 100 |
| Raw candidates generated | 9,499 |
| Candidates after deduplication | 395 |
| Shortlisted candidates | 50 |
| Scenes without valid-duration candidates | 0 |
| Successful LLM evaluations | 48 |
| Failed LLM evaluations | 2 |
| LLM evaluation success rate | 96% |

The two failed evaluations were rejected because the generated hook or cliffhanger quote did not match the source candidate exactly.

## 8. Output Files

- `parsed.json`: Parsed screenplay data containing scenes and timed elements.
- `promos.json`: Structured promotional candidate results, scores, quotes and risk flags.
- `promos.csv`: Spreadsheet-friendly candidate results.
- `ranked_report.md`: Top 10 LLM-ranked candidates with evaluation details.
- `failure_analysis.md`: Dataset statistics, evaluation failures and limitations.
- `human_review.csv`: Template for recording manual editorial ratings.

## 9. Setup and Execution

### Create and activate a virtual environment

```cmd
python -m venv venv
```

Windows CMD:

```cmd
venv\Scripts\activate
```

### Install dependencies

```cmd
pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file in the project root:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

Do not commit `.env` or expose API keys in the repository.

### Run screenplay parsing

```cmd
python parse.py --input data --out outputs/parsed.json
```

### Run the complete pipeline

```cmd
python run.py
```

The pipeline generates the JSON, CSV, ranked report and failure analysis in the `outputs/` directory.

## 10. Limitations and Future Work

- Heuristic screening may exclude strong promotional moments before LLM evaluation.
- LLM judgments are subjective and may vary between evaluations.
- Quote validation does not replace complete manual editorial verification.
- Temporal deduplication does not guarantee story-level diversity.
- Multi-segment promos combining different scenes or episodes have not been implemented.
- Human review of the shortlisted candidates remains pending.
- The current LLM evaluation is limited to the 50 shortlisted candidates rather than all generated candidates.

Potential improvements:
- Expand candidate screening to reduce missed promotional opportunities.
- Improve narrative coherence and standalone-context assessment.
- Compare LLM judgments against human editorial ratings.
- Explore multi-segment promo combinations.
- Add more comprehensive evaluation consistency checks.

## 11. Evaluation Status

The current implementation successfully parses all 50 screenplays, generates candidate windows, performs heuristic scoring and temporal deduplication, and evaluates the shortlisted candidates using Groq.

Of the 50 shortlisted candidates, 48 received valid LLM evaluations. The remaining 2 were rejected by quote validation.

The generated ranking is a preliminary editorial ranking. Human review is still required before treating the selected segments as production-ready promotional advertisements.