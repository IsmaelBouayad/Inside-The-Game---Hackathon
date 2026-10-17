from pydantic import BaseModel, Field
from typing import List, Literal

class Claim(BaseModel):
    actor_team: Literal["Meteor City", "Nova FC"]
    # Actions strictement limitées aux états possibles du Détecteur
    action: Literal["pressed", "lost_passes", "escaped_press"]
    # min_length=1 empêche le LLM de renvoyer une liste de preuves vide
    cited_event_ids: List[str] = Field(min_length=1)
    narrative: str

class ExplainerOutput(BaseModel):
    claims: List[Claim]

class EditorLLMOutput(BaseModel):
    analyst_view: str
    fan_view: str
    language_used: str
    target_persona: str
