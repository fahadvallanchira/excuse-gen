import json
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Round(BaseModel):
    excuse: str
    believability: int
    holes: list[str]
    verdict: Literal["accept", "revise"]

    @field_validator("verdict", mode="before")
    @classmethod
    def _lower_verdict(cls, v):
        return v.strip().lower() if isinstance(v, str) else v


class SwarmResult(BaseModel):
    rounds: list[Round] = Field(min_length=1)

    @property
    def final_excuse(self) -> str:
        return self.rounds[-1].excuse


def _prose_fallback(text: str) -> SwarmResult:
    return SwarmResult(rounds=[Round(excuse=text, believability=0, holes=["unparsed output"], verdict="revise")])


def parse_result(text: str) -> SwarmResult:
    text = text.strip()
    if not text:
        raise ValueError("empty swarm output")
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return _prose_fallback(text)
    try:
        return SwarmResult.model_validate(json.loads(text[start : end + 1]))
    except ValueError:
        return _prose_fallback(text)
