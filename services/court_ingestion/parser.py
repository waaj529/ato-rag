"""Conservative paragraph-aware parser for official court judgment HTML."""

from dataclasses import dataclass
import html
from io import BytesIO
from html.parser import HTMLParser
import re
from zipfile import ZipFile

from pypdf import PdfReader


PARAGRAPH = re.compile(r"^\s*\[?(\d{1,4})\]?\s+(.+)$", re.S)
DATE = re.compile(r"\b(\d{1,2}\s+[A-Z][a-z]+\s+\d{4})\b")
LABELLED_DATE = re.compile(
    r"(?:date of judg(?:e)?ment|delivered)\W*(?:on\W*)?" + DATE.pattern,
    re.I,
)


@dataclass(frozen=True)
class ParsedJudgment:
    title: str
    decision_date: str | None
    judges: tuple[str, ...]
    paragraphs: tuple[tuple[int, str], ...]


class _JudgmentHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.blocks: list[str] = []
        self._tag: str | None = None
        self._text: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "nav", "footer"}:
            self._ignored += 1
        if not self._ignored and tag in {"title", "p", "li", "h1", "h2", "h3", "td"}:
            self._tag, self._text = tag, []

    def handle_endtag(self, tag: str) -> None:
        if not self._ignored and tag == self._tag:
            value = " ".join("".join(self._text).split())
            if value:
                self.title = value if tag == "title" else self.title
                self.blocks.append(value)
            self._tag, self._text = None, []
        if tag in {"script", "style", "nav", "footer"} and self._ignored:
            self._ignored -= 1

    def handle_data(self, data: str) -> None:
        if self._tag and not self._ignored:
            self._text.append(data)


def _html_blocks(body: bytes) -> tuple[str, list[str]]:
    parser = _JudgmentHTML()
    parser.feed(body.decode("utf-8", errors="replace"))
    return parser.title, parser.blocks


def _document_blocks(body: bytes, content_type: str) -> tuple[str, list[str]]:
    if content_type == "application/pdf":
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(body)).pages)
    elif content_type.endswith("wordprocessingml.document"):
        with ZipFile(BytesIO(body)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8", errors="replace")
        text = re.sub(r"<w:tab[^>]*/>", "\t", xml)
        text = re.sub(r"</w:p>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
    else:
        return _html_blocks(body)
    blocks = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    return blocks[0] if blocks else "", blocks


def _numbered_paragraphs(blocks: list[str]) -> dict[int, str]:
    paragraphs: dict[int, str] = {}
    current: int | None = None
    for block in blocks:
        match = PARAGRAPH.match(block)
        number = int(match.group(1)) if match else None
        last = max(paragraphs, default=0)
        if number is not None and number not in paragraphs and last < number <= last + 3:
            current = number
            paragraphs[current] = match.group(2).strip()
        elif current is not None:
            paragraphs[current] = f"{paragraphs[current]} {block}".strip()
    return {number: text for number, text in paragraphs.items() if len(text.split()) >= 5}


def _case_title(title_hint: str, blocks: list[str], citation: str) -> str:
    for index, block in enumerate(blocks[:80]):
        if citation.casefold() not in block.casefold():
            continue
        if re.search(r"\bv\b", block, re.I):
            return block
        names = [value for value in blocks[max(0, index - 6):index]
                 if re.search(r"\bv\b", value, re.I) and len(value) < 200]
        if names:
            return f"{' / '.join(dict.fromkeys(names))} {citation}"
        return block
    return title_hint


def parse_judgment(body: bytes, expected_citation: str,
                   content_type: str = "text/html") -> ParsedJudgment:
    title_hint, blocks = _document_blocks(body, content_type)
    evidence = " ".join([title_hint, *blocks[:80]])
    if expected_citation.casefold() not in evidence.casefold():
        raise ValueError("official page does not corroborate the seeded neutral citation")
    paragraphs = _numbered_paragraphs(blocks)
    if not paragraphs:
        raise ValueError("official page contains no numbered judgment paragraphs")
    date = LABELLED_DATE.search(evidence) or DATE.search(evidence)
    judges = tuple(block for block in blocks[:40]
                   if re.search(r"\b(?:CJ|J|JJ)\b", block) and len(block) < 160)
    title = _case_title(title_hint, blocks, expected_citation)
    return ParsedJudgment(title, date.group(1) if date else None, judges, tuple(sorted(paragraphs.items())))
