from pathlib import Path

from app.characters import extract_known_characters
from app.models import Chapter, Chunk


def chunk_chapter(
    chapter: Chapter,
    max_chars: int = 1200,
    overlap_chars: int = 150,
    known_characters: list[str] | None = None,
) -> list[Chunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than 0")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be 0 or greater")

    base_contents = _build_base_chunks(chapter.paragraphs, max_chars)
    contents = _apply_overlap(base_contents, overlap_chars)
    return [
        _make_chunk(chapter, index, content, known_characters or [])
        for index, content in enumerate(contents)
        if content.strip()
    ]


def _build_base_chunks(paragraphs: list[str], max_chars: int) -> list[str]:
    chunks = []
    current = []

    for paragraph in paragraphs:
        clean_paragraph = paragraph.strip()
        if not clean_paragraph:
            continue
        if len(clean_paragraph) > max_chars:
            if current:
                chunks.append("\n\n".join(current))
                current = []
            chunks.extend(_split_long_paragraph(clean_paragraph, max_chars))
            continue

        candidate = "\n\n".join([*current, clean_paragraph]) if current else clean_paragraph
        if len(candidate) <= max_chars:
            current = [*current, clean_paragraph]
        else:
            chunks.append("\n\n".join(current))
            current = [clean_paragraph]

    if current:
        chunks.append("\n\n".join(current))
    return [chunk for chunk in chunks if chunk.strip()]


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    return [
        paragraph[index : index + max_chars].strip()
        for index in range(0, len(paragraph), max_chars)
        if paragraph[index : index + max_chars].strip()
    ]


def _apply_overlap(contents: list[str], overlap_chars: int) -> list[str]:
    if overlap_chars == 0:
        return contents

    overlapped = []
    for index, content in enumerate(contents):
        if index == 0:
            overlapped.append(content)
            continue
        overlap = _trailing_paragraph_overlap(contents[index - 1], overlap_chars)
        overlapped.append(f"{overlap}\n\n{content}" if overlap else content)
    return overlapped


def _trailing_paragraph_overlap(content: str, overlap_chars: int) -> str:
    selected = []
    total_length = 0
    for paragraph in reversed(content.split("\n\n")):
        clean_paragraph = paragraph.strip()
        if not clean_paragraph:
            continue
        separator_length = 2 if selected else 0
        next_length = total_length + separator_length + len(clean_paragraph)
        if next_length > overlap_chars:
            break
        selected = [clean_paragraph, *selected]
        total_length = next_length
    return "\n\n".join(selected)


def _make_chunk(
    chapter: Chapter,
    chunk_index: int,
    content: str,
    known_characters: list[str],
) -> Chunk:
    source_stem = Path(chapter.source_file).stem
    chapter_part = f"ch{chapter.chapter_number}" if chapter.chapter_number is not None else "ch_unknown"
    characters = extract_known_characters(content, known_characters)
    return Chunk(
        id=f"{source_stem}:{chapter_part}:chunk{chunk_index}",
        source_file=chapter.source_file,
        chapter_number=chapter.chapter_number,
        chapter_title=chapter.chapter_title,
        chunk_index=chunk_index,
        content=content,
        char_count=len(content),
        characters=characters,
    )
