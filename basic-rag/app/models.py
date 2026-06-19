from dataclasses import dataclass, field


@dataclass(frozen=True)
class Chapter:
    source_file: str
    chapter_number: int | None
    chapter_title: str | None
    raw_text: str
    paragraphs: list[str]


@dataclass(frozen=True)
class Chunk:
    id: str
    source_file: str
    chapter_number: int | None
    chapter_title: str | None
    chunk_index: int
    content: str
    char_count: int
    language: str = "th"
    characters: list[str] = field(default_factory=list)
