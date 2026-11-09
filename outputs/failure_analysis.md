# Failure Analysis and Limitations

## Dataset processing

- Episodes processed: 50
- Scenes processed: 100
- Scenes without valid-duration candidates: 14
- Raw candidates: 9499
- Candidates after temporal deduplication: 395
- Candidates shortlisted: 50

## LLM evaluation

- Successfully evaluated: 48
- Failed evaluations: 2
- Provider: Groq
- Model: openai/gpt-oss-20b

## Known limitations

1. Heuristic screening may miss strong narrative moments or retain weak candidates.
2. LLM judgments are subjective and may vary between evaluations.
3. Temporal deduplication does not guarantee story-level diversity.
4. Candidate boundaries align with timed-element boundaries, but editorial continuity requires human review.
5. Multi-segment promos have not been implemented.
6. Quote verification checks source-text presence and timing windows, but does not replace manual verification.

## Recommended improvements

- Review the highest-ranked promos manually.
- Compare LLM judgments with human ratings.
- Inspect low-confidence and failed evaluations.
- Review standalone clarity and narrative continuity.
- Explore multi-segment promo combinations.
