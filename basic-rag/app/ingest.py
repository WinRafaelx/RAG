import argparse
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from app.characters import load_known_characters
from app.chunker import chunk_chapter
from app.models import Chapter, Chunk
from app.utils import clean_text

CHAPTER_TITLE_PATTERN = re.compile(r"^\u0e15\u0e2d\u0e19\u0e17\u0e35\u0e48\s+(\d+)\s+[\u2014-]\s+(.+)$")


def parse_chapter_file(path: str | Path) -> Chapter:
    chapter_path = Path(path)
    if not chapter_path.exists():
        raise FileNotFoundError(f"Chapter file not found: {chapter_path}")
    if chapter_path.suffix.lower() != ".txt":
        raise ValueError(f"Expected a .txt chapter file: {chapter_path}")

    raw_text = clean_text(chapter_path.read_text(encoding="utf-8"))
    lines = raw_text.splitlines()
    first_index = _first_non_empty_line_index(lines)
    if first_index is None:
        return Chapter(
            source_file=chapter_path.name,
            chapter_number=None,
            chapter_title=None,
            raw_text=raw_text,
            paragraphs=[],
        )

    chapter_number, chapter_title = _parse_chapter_metadata(lines[first_index])
    body = "\n".join(lines[first_index + 1 :]).strip()
    paragraphs = _split_paragraphs(body)
    return Chapter(
        source_file=chapter_path.name,
        chapter_number=chapter_number,
        chapter_title=chapter_title,
        raw_text=raw_text,
        paragraphs=paragraphs,
    )


def chunks_to_dicts(chunks: list[Chunk]) -> list[dict]:
    return [asdict(chunk) for chunk in chunks]


def export_chunks_to_json(chunks: list[Chunk], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(chunks_to_dicts(chunks), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ingest_chapter_file(
    chapter_file: str | Path,
    output_dir: str | Path | None = None,
    known_characters: list[str] | None = None,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> tuple[Chapter, list[Chunk], Path | None]:
    chapter_path = Path(chapter_file)
    chapter = parse_chapter_file(chapter_path)
    chunks = chunk_chapter(
        chapter,
        max_chars=max_chars,
        overlap_chars=overlap_chars,
        known_characters=known_characters,
    )
    output_path = None
    if output_dir is not None:
        output_path = Path(output_dir) / f"{chapter_path.stem}.json"
        export_chunks_to_json(chunks, output_path)
    return chapter, chunks, output_path


def ingest_path(
    input_path: str | Path,
    output_dir: str | Path | None = None,
    known_characters: list[str] | None = None,
    max_chars: int = 1200,
    overlap_chars: int = 150,
) -> list[tuple[Chapter, list[Chunk], Path | None]]:
    path = Path(input_path)
    if path.is_file():
        return [
            ingest_chapter_file(
                path,
                output_dir=output_dir,
                known_characters=known_characters,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
        ]
    if path.is_dir():
        chapter_files = sorted(file_path for file_path in path.glob("*.txt") if file_path.is_file())
        if not chapter_files:
            raise FileNotFoundError(f"No .txt chapter files found in directory: {path}")
        return [
            ingest_chapter_file(
                chapter_file,
                output_dir=output_dir,
                known_characters=known_characters,
                max_chars=max_chars,
                overlap_chars=overlap_chars,
            )
            for chapter_file in chapter_files
        ]
    raise FileNotFoundError(f"Input path not found: {path}")


def _first_non_empty_line_index(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.strip():
            return index
    return None


def _parse_chapter_metadata(line: str) -> tuple[int | None, str | None]:
    match = CHAPTER_TITLE_PATTERN.match(line.strip())
    if not match:
        return None, None
    return int(match.group(1)), match.group(2).strip()


def _split_paragraphs(body: str) -> list[str]:
    return [paragraph.strip() for paragraph in re.split(r"\n\s*\n+", body) if paragraph.strip()]


def _preview_chunks(chunks: list[Chunk]) -> str:
    previews = []
    for chunk in chunks:
        preview = chunk.content[:300].replace("\n", "\\n")
        previews.append(f"- {chunk.id}: {preview}")
    return "\n".join(previews)


def _print_chapter_summary(chapter: Chapter, chunks: list[Chunk], output_path: Path | None = None) -> None:
    print(f"source file: {chapter.source_file}")
    print(f"chapter number: {chapter.chapter_number}")
    print(f"chapter title: {chapter.chapter_title}")
    print(f"paragraph count: {len(chapter.paragraphs)}")
    print(f"chunk count: {len(chunks)}")
    print(_preview_chunks(chunks))
    if output_path:
        print(f"wrote json: {output_path}")


def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> None:
    _configure_utf8_output()
    parser = argparse.ArgumentParser(description="Ingest and chunk Thai novel chapter files.")
    parser.add_argument("input_path", type=Path, help="A .txt chapter file or a directory of .txt chapters.")
    parser.add_argument("--out", type=Path, help="Output JSON file for one input file, or output directory for a directory input.")
    parser.add_argument("--characters", type=Path, help="Optional known character names file.")
    parser.add_argument("--max-chars", type=int, default=1200)
    parser.add_argument("--overlap-chars", type=int, default=150)
    args = parser.parse_args()

    known_characters = load_known_characters(args.characters) if args.characters else None
    if args.input_path.is_file():
        chapter = parse_chapter_file(args.input_path)
        chunks = chunk_chapter(
            chapter,
            max_chars=args.max_chars,
            overlap_chars=args.overlap_chars,
            known_characters=known_characters,
        )
        output_path = args.out
        if output_path:
            export_chunks_to_json(chunks, output_path)
        _print_chapter_summary(chapter, chunks, output_path)
        return

    output_dir = args.out if args.out else Path("chunks")
    results = ingest_path(
        args.input_path,
        output_dir=output_dir,
        known_characters=known_characters,
        max_chars=args.max_chars,
        overlap_chars=args.overlap_chars,
    )
    total_chunks = sum(len(chunks) for _, chunks, _ in results)
    print(f"processed files: {len(results)}")
    print(f"total chunks: {total_chunks}")
    print(f"output directory: {output_dir}")


if __name__ == "__main__":
    main()
