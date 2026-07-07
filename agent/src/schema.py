from pydantic import BaseModel
from typing import Literal


class Table(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    caption: str | None = None


class Card(BaseModel):
    name: str
    tier: str | None = None
    reasoning: str
    metrics: dict[str, str]


class Section(BaseModel):
    heading: str
    content: str | Table | list[Card]
    type: Literal["text", "table", "cards", "ranking"]


class Report(BaseModel):
    date: str
    type: Literal["daily-pulse", "weekly-review", "swing-analysis", "portfolio-audit"]
    title: str
    tags: list[str]
    summary: str
    slug: str
    sections: list[Section]
    generatedAt: str
    model: str
