# AI Tools Usage Note
## KukuFM Assignment – Find the Promos (Ads)

AI tools were used as development and research assistants during the implementation of this assignment.

### 1. ChatGPT
Used for:
- Understanding the problem requirements and planning the system architecture.
- Discussing candidate-generation strategies, heuristic filtering and ranking.
- Debugging implementation issues and refining the Python pipeline.
- Designing the LLM evaluation criteria and structured output schema.
- Reviewing results, identifying limitations and preparing documentation.

### 2. Groq API – GPT-OSS 20B
Used for:
- Evaluating shortlisted promotional candidates.
- Scoring hook quality, cliffhanger strength, standalone clarity and overall effectiveness.
- Generating explanations, context descriptions, confidence levels and risk flags.

### 3. Development and Validation
The implementation was developed and tested in Python. Deterministic parsing, timestamp validation, candidate generation, heuristic scoring, deduplication, caching, output generation and response validation were implemented as part of the project.

AI-generated evaluations were treated as recommendations rather than verified editorial judgments. Human review remains a recommended next step.

### 4. Transparency
The final results are based on the implemented pipeline and the recorded execution statistics. AI tools assisted with development and evaluation, but their outputs were subject to programmatic validation and documented limitations.