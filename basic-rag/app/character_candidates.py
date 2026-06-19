import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from app.utils import clean_text

THAI_CHARS = "\u0e01-\u0e3a\u0e40-\u0e4e"
NAME_PREFIXES = [
    "ช็อง",
    "แบ็ก",
    "ฮยอน",
    "อุน",
    "จาง",
    "โซ",
    "ยู",
    "ยุน",
    "มู",
    "โจ",
    "ถัง",
    "นัม",
    "อี",
    "กวัก",
    "มง",
    "กึม",
    "พย็อก",
    "ตัง",
    "วี",
    "ฮง",
]
CONTEXT_VERBS = [
    "กล่าว",
    "ถาม",
    "ตอบ",
    "ตะโกน",
    "พึมพำ",
    "หัวเราะ",
    "มอง",
    "พยักหน้า",
    "ส่ายหน้า",
    "เอ่ย",
    "ร้อง",
    "ถอนหายใจ",
    "เดิน",
    "ยิ้ม",
    "จ้อง",
]
STOPWORDS = {
    "ท่านเจ้าสำนัก",
    "เจ้าสำนัก",
    "ผู้อาวุโส",
    "ศิษย์",
    "สำนัก",
    "กระบี่",
    "พวกเขา",
    "พวกเรา",
    "อีกฝ่าย",
    "อีกต่อไป",
    "อีกคน",
    "โจรป่า",
    "โจรสลัดมังกรดำ",
    "ซาน",
    "ฮยอน",
    "ยู",
    "ยู่",
    "อี",
}
TRAILING_PARTICLES = [
    "ที่กำลัง",
    "ทอดสายตา",
    "ทำเพียงแค่",
    "ทำได้เพียง",
    "ระเบิดเสียง",
    "กวาดสายตา",
    "แผดเสียง",
    "ชี้ชวนให้",
    "ระบายรอย",
    "แค่นเสียง",
    "ตวัดไปจับ",
    "เผยรอย",
    "และยุนจง",
    "ที่เฝ้า",
    "ผู้ซึ่ง",
    "พากัน",
    "กำลัง",
    "ยังคง",
    "ต่าง",
    "ทุกคน",
    "กลับ",
    "พลัน",
    "ทอด",
    "ก้าวเท้า",
    "กระตุก",
    "พยายาม",
    "หันไป",
    "ตวัด",
    "เริ่ม",
    "เฝ้า",
    "ไม่ได้",
    "ได้แต่",
    "เหลือบ",
    "ร่วม",
    "หลุด",
    "แล้ว",
    "บ่น",
    "เคย",
    "มัก",
    "ฉีก",
    "ถูก",
    "ก้าว",
    "บิด",
    "ส่ง",
    "เอง",
    "ผู้",
    "ลอบ",
    "รีบ",
    "ยก",
    "เห็น",
    "ก็",
    "ที่",
    "จะ",
]
MAX_SAMPLES = 3
SNIPPET_RADIUS = 45


@dataclass(frozen=True)
class CharacterCandidate:
    name: str
    total_count: int
    context_hits: int
    files: list[str]
    samples: list[str]


def extract_candidate_names(text: str) -> list[str]:
    names = []
    for match in _context_pattern().finditer(text):
        candidate = _clean_candidate(match.group("name"))
        if _is_valid_candidate(candidate):
            names.append(candidate)
    return names


def discover_character_candidates(
    data_dir: str | Path,
    min_count: int = 2,
    limit: int = 200,
) -> list[CharacterCandidate]:
    chapter_files = _chapter_files(data_dir)
    context_counts = Counter()
    total_counts = Counter()
    files_by_name: dict[str, set[str]] = defaultdict(set)
    samples_by_name: dict[str, list[str]] = defaultdict(list)
    chapter_texts = []

    for chapter_file in chapter_files:
        text = clean_text(chapter_file.read_text(encoding="utf-8"))
        chapter_texts.append((chapter_file, text))
        names = extract_candidate_names(text)
        context_counts.update(names)

    for chapter_file, text in chapter_texts:
        for name in context_counts:
            count = text.count(name)
            if count == 0:
                continue
            total_counts[name] += count
            files_by_name[name].add(chapter_file.name)
            _add_sample(samples_by_name[name], text, name)

    candidates = [
        CharacterCandidate(
            name=name,
            total_count=total_counts[name],
            context_hits=context_counts[name],
            files=sorted(files_by_name[name]),
            samples=samples_by_name[name],
        )
        for name in total_counts
        if total_counts[name] >= min_count
    ]
    return sorted(candidates, key=lambda item: (-item.total_count, -item.context_hits, item.name))[:limit]


def write_candidates_markdown(candidates: list[CharacterCandidate], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Character Candidates",
        "",
        "Review this list before copying real names into `characters.txt`.",
        "",
    ]
    for index, candidate in enumerate(candidates, start=1):
        lines.extend(
            [
                f"## {index}. {candidate.name}",
                "",
                f"- total_count: {candidate.total_count}",
                f"- context_hits: {candidate.context_hits}",
                f"- files: {', '.join(candidate.files[:12])}",
                "- samples:",
            ]
        )
        lines.extend(f"  - {sample}" for sample in candidate.samples)
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_candidates_json(candidates: list[CharacterCandidate], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(candidate) for candidate in candidates], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _context_pattern() -> re.Pattern:
    prefix_pattern = "|".join(re.escape(prefix) for prefix in NAME_PREFIXES)
    verb_pattern = "|".join(re.escape(verb) for verb in CONTEXT_VERBS)
    return re.compile(
        rf"(?P<name>(?:{prefix_pattern})[{THAI_CHARS}]{{0,18}}?)(?={verb_pattern})"
    )


def _chapter_files(data_dir: str | Path) -> list[Path]:
    path = Path(data_dir)
    if not path.exists():
        raise FileNotFoundError(f"Data directory not found: {path}")
    if not path.is_dir():
        raise ValueError(f"Expected a directory of .txt files: {path}")
    files = sorted(file_path for file_path in path.glob("*.txt") if file_path.is_file())
    if not files:
        raise FileNotFoundError(f"No .txt files found in: {path}")
    return files


def _clean_candidate(candidate: str) -> str:
    cleaned = candidate.strip(" \t\n\r\"'“”‘’.,!?…()[]{}")
    previous = None
    while previous != cleaned:
        previous = cleaned
        for particle in TRAILING_PARTICLES:
            if cleaned.endswith(particle) and len(cleaned) - len(particle) >= 4:
                cleaned = cleaned[: -len(particle)]
                break
    return cleaned


def _is_valid_candidate(candidate: str) -> bool:
    return (
        4 <= len(candidate) <= 24
        and candidate not in STOPWORDS
        and candidate not in NAME_PREFIXES
        and not candidate.startswith(("ซาน", "ยู่", "อีก"))
        and not (candidate.startswith("โซ") and len(candidate) <= 5)
        and "แห่ง" not in candidate
        and "โจร" not in candidate
        and any(candidate.startswith(prefix) for prefix in NAME_PREFIXES)
    )


def _add_sample(samples: list[str], text: str, name: str) -> None:
    if len(samples) >= MAX_SAMPLES:
        return
    index = text.find(name)
    if index < 0:
        return
    start = max(0, index - SNIPPET_RADIUS)
    end = min(len(text), index + len(name) + SNIPPET_RADIUS)
    snippet = text[start:end].replace("\n", " ").strip()
    if snippet and snippet not in samples:
        samples.append(snippet)


def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")


def main() -> None:
    _configure_utf8_output()
    parser = argparse.ArgumentParser(description="Extract likely Thai novel character name candidates.")
    parser.add_argument("data_dir", type=Path, help="Directory containing chapter .txt files.")
    parser.add_argument("--out", type=Path, default=Path("character_candidates.md"))
    parser.add_argument("--json", type=Path, help="Optional JSON output path.")
    parser.add_argument("--min-count", type=int, default=2)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    candidates = discover_character_candidates(
        args.data_dir,
        min_count=args.min_count,
        limit=args.limit,
    )
    write_candidates_markdown(candidates, args.out)
    if args.json:
        write_candidates_json(candidates, args.json)
    print(f"found candidates: {len(candidates)}")
    print(f"wrote markdown: {args.out}")
    if args.json:
        print(f"wrote json: {args.json}")


if __name__ == "__main__":
    main()
