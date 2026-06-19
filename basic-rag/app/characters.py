from pathlib import Path


def extract_known_characters(text: str, known_names: list[str]) -> list[str]:
    matches = []
    for name in known_names:
        index = text.find(name)
        if index >= 0:
            matches.append((index, name))
    return [name for _, name in sorted(matches, key=lambda item: item[0])]


def load_known_characters(path: str | Path) -> list[str]:
    character_path = Path(path)
    if not character_path.exists():
        raise FileNotFoundError(f"Character file not found: {character_path}")
    return [
        line.strip()
        for line in character_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
