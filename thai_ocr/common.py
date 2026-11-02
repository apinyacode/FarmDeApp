"""Shared paths, data shapes and the review text format used by every step.

Folder layout for one PDF (everything lives under work/<pdf name>/):

    pages/page_001.jpg            full scanned page                    (step 1)
    review/page_001.jpg           just the handwriting, enlarged       (step 1)
    review/page_001_REVIEW.txt    Claude's text, waiting to be checked (step 2)
    review/page_001_DONE.txt      same file after a person checked it and renamed it
    ai/page_001.json              Claude's original answer             (step 2) - never edited

Step 2 never overwrites a text file that already exists, so re-running it
can't lose anything a person corrected.
"""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
WORK_DIR = ROOT / "work"

# Words Claude is unsure about are written like ⟦สติ?⟧ inside the lines.
UNSURE_PATTERN = re.compile(r"⟦(.+?)⟧")


class Correction(BaseModel):
    """One spelling mistake that was fixed, so a reviewer can see what the paper says."""

    line: int = Field(description="Line number in `lines`, starting at 1.")
    as_written: str = Field(description="The word exactly as the writer spelled it.")
    corrected: str = Field(description="The correct spelling used in `lines`.")


class PageTranscription(BaseModel):
    """What Claude must return for each page (enforced by structured outputs)."""

    lines: list[str] = Field(
        description="Transcription, one entry per handwritten line, in the same order and with "
        "the same line breaks as the paper. Spelling mistakes are corrected (each one listed in "
        "`corrections`); wording is otherwise unchanged. Wrap any word you are not sure about "
        "like ⟦word?⟧."
    )
    corrections: list[Correction] = Field(
        description="Every spelling mistake you corrected in `lines`. Empty if none."
    )
    greeting: str = Field(description="Opening salutation, e.g. กราบนมัสการพระอาจารย์... Empty if none.")
    question: str = Field(
        description="The body of the question as one clean paragraph: the corrected lines "
        "joined, without the greeting and closing."
    )
    closing: str = Field(description="Closing/thanks line, e.g. ขอบพระคุณเจ้าค่ะ. Empty if none.")
    continues_from_previous: bool = Field(
        description="True if this page looks like the 2nd+ page of a question (e.g. numbered ②)."
    )
    continues_to_next: bool = Field(
        description="True if the question clearly continues on the next page (arrow, numbering)."
    )
    notes: str = Field(
        description="Anything a reviewer should know, in Thai or English: underlines, crossed-out "
        "words, non-Thai words, drawings, illegible parts."
    )
    confidence: Literal["high", "medium", "low"]


def work_dir_for(pdf_name: str) -> Path:
    return WORK_DIR / pdf_name


def page_name(number: int) -> str:
    return f"page_{number:03d}"


def list_pages(doc_dir: Path) -> list[str]:
    return sorted(p.stem for p in (doc_dir / "pages").glob("page_*.jpg"))


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False keeps Thai readable if you open the file in an editor.
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def unsure_words(lines: list[str]) -> list[str]:
    return [m for line in lines for m in UNSURE_PATTERN.findall(line)]


# ---------------------------------------------------------------- review text files

REVIEW_FILE = re.compile(r"^(page_\d+)_([A-Za-z]+)\.txt$")
SECTIONS = {
    "text": "== TEXT (same line breaks as the paper) ==",
    "clean": "== CLEAN VERSION (one paragraph) ==",
    "fixes": "== SPELLING FIXES (as written -> corrected) ==",
    "notes": "== NOTES ==",
}


def review_files(doc_dir: Path) -> dict[str, tuple[Path, str]]:
    """{page: (text file, status)} where status is the word in the file name, e.g. REVIEW or DONE."""
    found = {}
    for path in sorted((doc_dir / "review").glob("page_*.txt")):
        match = REVIEW_FILE.match(path.name)
        if match:
            found[match.group(1)] = (path, match.group(2).upper())
    return found


def render_review_text(page: str, data: dict) -> str:
    """Turn Claude's answer into the text file a person reviews."""
    lines = data.get("lines", [])
    fixes = data.get("corrections", [])
    notes = [data.get("notes", "").strip()]
    if data.get("continues_from_previous"):
        notes.append("Continues from the previous page.")
    if data.get("continues_to_next"):
        notes.append("Continues on the next page.")
    clean = " ".join(filter(None, [data.get("greeting"), data.get("question"), data.get("closing")]))
    return "\n".join([
        f"# {page}  |  confidence: {data.get('confidence', '?')}  |  "
        f"unsure words: {len(unsure_words(lines))}  |  spelling fixes: {len(fixes)}",
        f"# Compare with {page}.jpg in this folder. Fix the text, and remove the ⟦ ⟧ around words you checked.",
        f"# When finished, rename this file from {page}_REVIEW.txt to {page}_DONE.txt",
        "# (Lines starting with # are help text and are ignored.)",
        "",
        SECTIONS["text"],
        *lines,
        "",
        SECTIONS["clean"],
        clean,
        "",
        SECTIONS["fixes"],
        *[f"line {fix['line']}: {fix['as_written']} -> {fix['corrected']}" for fix in fixes],
        "",
        SECTIONS["notes"],
        " ".join(filter(None, notes)),
        "",
    ])


def parse_review_text(text: str) -> dict[str, str]:
    """Read a (possibly edited) review file back into {text, clean, fixes, notes}."""
    headers = {header: key for key, header in SECTIONS.items()}
    parts = {key: [] for key in SECTIONS}
    current = None
    for line in text.splitlines():
        if line.startswith("#"):
            continue
        if line.strip() in headers:
            current = headers[line.strip()]
        elif current:
            parts[current].append(line.rstrip())
    return {key: "\n".join(value).strip() for key, value in parts.items()}
