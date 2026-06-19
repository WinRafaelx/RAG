import argparse
import posixpath
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET


class TextExtractor(HTMLParser):
    block_tags = {"h1", "h2", "h3", "p", "div", "br"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_body = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.in_body = True
            return
        if self.in_body and tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "body":
            self.in_body = False
            return
        if self.in_body and tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_body:
            self.parts.append(data)

    def text(self):
        raw = "".join(self.parts)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.splitlines()]
        clean_lines = []
        previous_blank = True
        for line in lines:
            if not line:
                if not previous_blank:
                    clean_lines.append("")
                previous_blank = True
                continue
            clean_lines.append(line)
            previous_blank = False
        return "\n".join(clean_lines).strip() + "\n"


def read_container_root(epub):
    container = ET.fromstring(epub.read("META-INF/container.xml"))
    namespace = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = container.find(".//c:rootfile", namespace)
    if rootfile is None:
        raise RuntimeError("Could not find EPUB rootfile in META-INF/container.xml")
    return rootfile.attrib["full-path"]


def chapter_items(epub, opf_path):
    opf = ET.fromstring(epub.read(opf_path))
    namespace = {"opf": "http://www.idpf.org/2007/opf"}
    manifest = {
        item.attrib["id"]: item.attrib["href"]
        for item in opf.findall(".//opf:manifest/opf:item", namespace)
    }
    spine_ids = [
        itemref.attrib["idref"]
        for itemref in opf.findall(".//opf:spine/opf:itemref", namespace)
    ]
    opf_dir = posixpath.dirname(opf_path)
    chapters = []
    for item_id in spine_ids:
        href = manifest.get(item_id)
        if href and re.search(r"chapter_\d+_\d+\.xhtml$", href):
            chapters.append(posixpath.normpath(posixpath.join(opf_dir, href)))
    return chapters


def safe_stem(chapter_path):
    match = re.search(r"chapter_(\d+)_(\d+)\.xhtml$", chapter_path)
    if not match:
        return Path(chapter_path).stem
    index, chapter_number = match.groups()
    return f"{int(index):03d}_chapter_{chapter_number}"


def extract(epub_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(epub_path) as epub:
        opf_path = read_container_root(epub)
        chapters = chapter_items(epub, opf_path)
        if not chapters:
            raise RuntimeError("No chapter XHTML files found in EPUB spine")

        written = []
        for chapter in chapters:
            parser = TextExtractor()
            parser.feed(epub.read(chapter).decode("utf-8", errors="replace"))
            text = parser.text()
            output_path = output_dir / f"{safe_stem(chapter)}.txt"
            output_path.write_text(text, encoding="utf-8")
            written.append(output_path)
    return written


def main():
    parser = argparse.ArgumentParser(description="Extract EPUB chapters to separate TXT files.")
    parser.add_argument("epub", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("chapters_txt"))
    args = parser.parse_args()

    written = extract(args.epub, args.output)
    print(f"Wrote {len(written)} chapter files to {args.output}")


if __name__ == "__main__":
    main()
