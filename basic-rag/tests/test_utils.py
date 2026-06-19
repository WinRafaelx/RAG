from app.utils import clean_text


def test_clean_text_preserves_thai_dialogue_and_punctuation():
    raw = "ตอนที่ 724 — ข้ากลับมาแล้ว (4)  \r\n\r\n\r\n“ข้าไม่เข้าใจเลยจริงๆ...”  \r\n‘ใช่หรือไม่?’\r\n"

    cleaned = clean_text(raw)

    assert cleaned == "ตอนที่ 724 — ข้ากลับมาแล้ว (4)\n\n“ข้าไม่เข้าใจเลยจริงๆ...”\n‘ใช่หรือไม่?’"


def test_clean_text_collapses_three_or_more_blank_lines_to_two():
    raw = "ย่อหน้าแรก\n\n\n\nย่อหน้าสอง"

    cleaned = clean_text(raw)

    assert cleaned == "ย่อหน้าแรก\n\nย่อหน้าสอง"
