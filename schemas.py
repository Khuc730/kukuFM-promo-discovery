
from typing import Literal
from pydantic import BaseModel, Field


class PromoJudgment(BaseModel):
    """
    Defines the expected response from the LLM judge.
    """

    hook_score: int = Field(
        ge=1,
        le=10,
        description="How effectively the opening grabs attention."
    )

    cliffhanger_score: int = Field(
        ge=1,
        le=10,
        description="How compelling the ending is."
    )

    standalone_score: int = Field(
        ge=1,
        le=10,
        description="How understandable the promo is to a new viewer."
    )

    overall_score: float = Field(
        ge=1,
        le=10,
        description="Overall promotional quality."
    )

    hook_quote: str = Field(
        description="A verbatim hook quote from the candidate."
    )

    cliffhanger: str = Field(
        description="A verbatim ending quote or action from the candidate."
    )

    why_it_works: str = Field(
        description="One-line explanation of the promo's effectiveness."
    )

    standalone_context: str = Field(
        description="Brief context that helps a new viewer understand the promo."
    )

    confidence: Literal["low", "medium", "high"]

    risk_flags: list[str] = Field(
        default_factory=list,
        description="Potential issues with the promo."
    )
