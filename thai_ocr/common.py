"""Shared paths and data shapes used by every step of the pipeline.

Folder layout for one PDF (everything lives under work/<pdf name>/):

    pages/page_001.jpg     full scanned page            (step 1)
    crops/page_001.jpg     just the handwritten slip    (step 1)
    ai/page_001.json       Claude's transcription       (step 2) - never edited by hand
    reviewed/page_001.json the human-checked version    (step 3) - never overwritten by step 2

Keeping "ai" and "reviewed" separate means you can re-run step 2 on a page
without losing anything a person already corrected.
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


def list_documents() -> list[str]:
    """Names of PDFs that have been through step 1."""
    if not WORK_DIR.exists():
        return []
    return sorted(p.name for p in WORK_DIR.iterdir() if (p / "pages").is_dir())


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


def best_version(doc_dir: Path, page: str) -> tuple[dict | None, str]:
    """The reviewed version if a person saved one, otherwise Claude's version.

    Returns (data, status) where status is one of:
    'approved', 'needs_check', 'ai_only', 'not_transcribed'.
    """
    reviewed = read_json(doc_dir / "reviewed" / f"{page}.json")
    if reviewed:
        return reviewed, reviewed.get("status", "needs_check")
    ai = read_json(doc_dir / "ai" / f"{page}.json")
    if ai:
        return ai, "ai_only"
    return None, "not_transcribed"
