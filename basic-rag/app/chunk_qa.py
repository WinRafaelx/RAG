import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SUSPICIOUS_STARTS = (
    "และ",
    "แต่",
    "ที่",
    "ก็",
    "จึง",
    "แล้ว",
    "ทว่า",
    "อย่างไรก็ตาม",
)
SOFT_ENDINGS = (",", "，", "、", "...")
DEFAULT_MIN_CHARS = 250
DEFAULT_MAX_CHARS = 1500
DEFAULT_LIMIT = 200


@dataclass(frozen=True)
class ChunkQAResult:
    file: str
    chunk_id: str
    chunk_index: int
    chapter_number: int | None
    char_count: int
    paragraph_count: int
    starts_with_dialogue: bool
    character_count: int
    characters: list[str]
    warnings: list[str]
    priority: int
    preview: str


def analyze_chunk(
    file_name: str,
    chunk: dict,
    min_chars: int = DEFAULT_MIN_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> ChunkQAResult:
    content = str(chunk.get("content", "")).strip()
    characters = list(chunk.get("characters") or [])
    warnings = _warnings_for_content(content, characters, min_chars, max_chars)
    return ChunkQAResult(
        file=file_name,
        chunk_id=str(chunk.get("id", "")),
        chunk_index=int(chunk.get("chunk_index", 0)),
        chapter_number=chunk.get("chapter_number"),
        char_count=len(content),
        paragraph_count=_paragraph_count(content),
        starts_with_dialogue=content.startswith(("“", "‘", '"', "'")),
        character_count=len(characters),
        characters=characters,
        warnings=warnings,
        priority=_priority_for_warnings(warnings),
        preview=_preview(content),
    )


def analyze_chunks_dir(
    chunks_dir: str | Path,
    min_chars: int = DEFAULT_MIN_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[ChunkQAResult]:
    paths = _chunk_json_files(chunks_dir)
    results = []
    for path in paths:
        chunks = json.loads(path.read_text(encoding="utf-8"))
        results.extend(
            analyze_chunk(path.name, chunk, min_chars=min_chars, max_chars=max_chars)
            for chunk in chunks
        )
    return sorted(results, key=lambda item: (-item.priority, item.file, item.chunk_index))


def write_qa_json(results: list[ChunkQAResult], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_qa_markdown(
    results: list[ChunkQAResult],
    output_path: str | Path,
    limit: int = DEFAULT_LIMIT,
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    selected = results[:limit]
    lines = [
        "# Chunk QA Report",
        "",
        f"Total chunks analyzed: {len(results)}",
        f"Chunks shown: {len(selected)}",
        "",
    ]
    for result in selected:
        warnings = ", ".join(result.warnings) if result.warnings else "none"
        characters = ", ".join(result.characters) if result.characters else "none"
        lines.extend(
            [
                f"## {result.file} / chunk {result.chunk_index}",
                "",
                f"- id: `{result.chunk_id}`",
                f"- priority: {result.priority}",
                f"- warnings: {warnings}",
                f"- char_count: {result.char_count}",
                f"- paragraph_count: {result.paragraph_count}",
                f"- characters: {characters}",
                "",
                "```text",
                result.preview,
                "```",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _warnings_for_content(
    content: str,
    characters: list[str],
    min_chars: int,
    max_chars: int,
) -> list[str]:
    warnings = []
    if not content:
        return ["empty_content"]
    if len(content) < min_chars:
        warnings.append("too_short")
    if len(content) > max_chars:
        warnings.append("too_long")
    if not characters:
        warnings.append("no_characters")
    if _has_suspicious_start(content):
        warnings.append("suspicious_start")
    if _has_unbalanced_dialogue_quotes(content):
        warnings.append("unbalanced_dialogue_quotes")
    if content.endswith(SOFT_ENDINGS):
        warnings.append("soft_ending")
    return warnings


def _priority_for_warnings(warnings: list[str]) -> int:
    weights = {
        "empty_content": 5,
        "too_short": 3,
        "too_long": 2,
        "no_characters": 1,
        "suspicious_start": 2,
        "unbalanced_dialogue_quotes": 2,
        "soft_ending": 1,
    }
    return sum(weights.get(warning, 1) for warning in warnings)


def _has_suspicious_start(content: str) -> bool:
    return any(content.startswith(prefix) for prefix in SUSPICIOUS_STARTS)


def _has_unbalanced_dialogue_quotes(content: str) -> bool:
    quote_pairs = (("“", "”"), ("‘", "’"), ('"', '"'))
    return any(content.count(open_quote) % 2 != content.count(close_quote) % 2 for open_quote, close_quote in quote_pairs)


def _paragraph_count(content: str) -> int:
    return len([paragraph for paragraph in content.split("\n\n") if paragraph.strip()])


def _preview(content: str, max_chars: int = 700) -> str:
    return content[:max_chars].strip()


def _chunk_json_files(chunks_dir: str | Path) -> list[Path]:
    path = Path(chunks_dir)
    if not path.exists():
        raise FileNotFoundError(f"Chunks directory not found: {path}")
    if not path.is_dir():
        raise ValueError(f"Expected a chunks directory: {path}")
    files = sorted(file_path for file_path in path.glob("*.json") if file_path.is_file())
    if not files:
        raise FileNotFoundError(f"No JSON chunk files found in: {path}")
    return files


def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> None:
    _configure_utf8_output()
    parser = argparse.ArgumentParser(description="Generate QA reports for chunk JSON files.")
    parser.add_argument("chunks_dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("chunk_quality_report.md"))
    parser.add_argument("--json", type=Path, default=Path("chunk_quality_report.json"))
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--min-chars", type=int, default=DEFAULT_MIN_CHARS)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    args = parser.parse_args()

    results = analyze_chunks_dir(args.chunks_dir, min_chars=args.min_chars, max_chars=args.max_chars)
    write_qa_markdown(results, args.out, limit=args.limit)
    write_qa_json(results, args.json)
    flagged = sum(1 for result in results if result.warnings)
    print(f"analyzed chunks: {len(results)}")
    print(f"flagged chunks: {flagged}")
    print(f"wrote markdown: {args.out}")
    print(f"wrote json: {args.json}")


if __name__ == "__main__":
    main()
