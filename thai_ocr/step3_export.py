"""Step 3: collect the reviewed text files into a CSV (opens in Excel / Google
Sheets) and a Word file that shows each scan next to its text.

Usage:
    python step3_export.py questions_2560
    python step3_export.py questions_2560 --done-only    # only pages renamed to _DONE

The text is read from work/<pdf name>/review/page_NNN_*.txt, including your
edits; the word after the page number (REVIEW, DONE, ...) becomes the status.
Files are written to work/<pdf name>/export/.
"""

import argparse
import csv

from docx import Document
from docx.shared import Cm, Pt

from common import list_pages, parse_review_text, read_json, review_files, work_dir_for

CSV_COLUMNS = ["page", "status", "confidence", "clean", "text", "spelling_fixes", "notes"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("document")
    parser.add_argument("--done-only", action="store_true", help="leave out pages not renamed to _DONE")
    args = parser.parse_args()

    doc_dir = work_dir_for(args.document)
    export_dir = doc_dir / "export"
    export_dir.mkdir(exist_ok=True)
    files = review_files(doc_dir)

    rows = []
    for page in list_pages(doc_dir):
        if page not in files:
            continue  # not transcribed yet
        path, status = files[page]
        if args.done_only and status != "DONE":
            continue
        parts = parse_review_text(path.read_text(encoding="utf-8"))
        ai = read_json(doc_dir / "ai" / f"{page}.json") or {}
        rows.append({
            "page": int(page.split("_")[1]),
            "status": status,
            "confidence": ai.get("confidence", ""),
            "clean": parts["clean"],
            "text": parts["text"],
            "spelling_fixes": parts["fixes"].replace("\n", "; "),
            "notes": parts["notes"],
        })

    # utf-8-sig adds a marker so Excel shows Thai correctly instead of garbled letters.
    csv_path = export_dir / f"{args.document}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    word = Document()
    word.styles["Normal"].font.size = Pt(14)
    word.add_heading(args.document, level=0)
    for row in rows:
        page = f"page_{row['page']:03d}"
        word.add_heading(f"Page {row['page']}  ({row['status']})", level=1)
        table = word.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        image_cell, text_cell = table.rows[0].cells
        image_cell.paragraphs[0].add_run().add_picture(str(doc_dir / "review" / f"{page}.jpg"), width=Cm(8))
        text_cell.paragraphs[0].add_run(row["text"])
        if row["clean"]:
            word.add_paragraph().add_run("Clean version: ").bold = True
            word.add_paragraph(row["clean"])
        if row["spelling_fixes"]:
            word.add_paragraph(f"Spelling fixed (as written -> corrected): {row['spelling_fixes']}")
        if row["notes"]:
            word.add_paragraph(f"Notes: {row['notes']}")
        word.add_page_break()
    docx_path = export_dir / f"{args.document}.docx"
    word.save(docx_path)

    done = sum(1 for row in rows if row["status"] == "DONE")
    print(f"Exported {len(rows)} page(s) ({done} DONE, {len(rows) - done} not yet):\n  {csv_path}\n  {docx_path}")


if __name__ == "__main__":
    main()
