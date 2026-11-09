
from pydantic import ValidationError
from schemas import PromoJudgment


# Test a valid judgment
valid_data = {
    "hook_score": 9,
    "cliffhanger_score": 8,
    "standalone_score": 7,
    "overall_score": 8.2,
    "hook_quote": "What were you doing there?",
    "cliffhanger": "What did you find?",
    "why_it_works": "An accusation leads into a mysterious discovery.",
    "standalone_context": "A husband questions his wife about a mysterious visit.",
    "confidence": "high",
    "risk_flags": []
}

judgment = PromoJudgment(**valid_data)

print("Valid judgment accepted!")
print(judgment.model_dump())


# Test an invalid score
invalid_data = valid_data.copy()
invalid_data["hook_score"] = 15

try:
    PromoJudgment(**invalid_data)
except ValidationError:
    print("\nInvalid score rejected successfully!")
