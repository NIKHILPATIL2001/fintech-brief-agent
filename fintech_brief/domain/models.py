"""Core domain model for a single news story."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Story:
    title: str
    link: str
    source: str
    firm: str
    published: str = ""
    synopsis: str = ""
    impact: str = "MEDIUM"
    category: str = "Other"
    entities: list[str] = field(default_factory=list)
    rank_score: int = 0
    pre_filter_score: int = 0
    learned_rank_adjustment: int = 0
