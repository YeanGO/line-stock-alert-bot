from pydantic import BaseModel


class RuleEvaluation(BaseModel):
    triggered: bool
    reason: str
