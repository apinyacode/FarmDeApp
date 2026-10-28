"""Step 2: ask Claude to transcribe each page. Saves one JSON file per page in
work/<pdf name>/ai/.

Usage:
    python step2_transcribe.py questions_2560                 # all pages not done yet
    python step2_transcribe.py questions_2560 --pages 3 7-9   # only these pages
    python step2_transcribe.py questions_2560 --pages 5 --force   # redo page 5

Needs an Anthropic API key:  set ANTHROPIC_API_KEY=...  (Windows)
                             export ANTHROPIC_API_KEY=...  (Mac/Linux)

Pages that already have a JSON file are skipped, so if the script stops
half-way you can just run it again.
"""

import argparse
import base64
import io
import time

import anthropic
from PIL import Image

from common import PageTranscription, list_pages, page_name, work_dir_for, write_json

MODEL = "claude-opus-5-5"
FULL_PAGE_MAX_SIDE = 1400  # the full page is only for context, so a smaller copy is enough

SYSTEM_PROMPT = """You transcribe scanned handwritten Thai documents for a digital archive.

The documents are question slips that lay practitioners wrote to a Buddhist meditation \
teacher (Thai year 2560). They usually open with a salutation such as \
"กราบนมัสการพระอาจารย์..." and close with thanks such as "ขอบพระคุณเจ้าค่ะ". They often \
contain Pali and Dhamma vocabulary (e.g. สติปัฏฐาน, จิตตานุปัสสนา, กิเลส, สมาธิ, วิปัสสนา) and \
names from the Pali canon (e.g. องคุลีมาล). Some slips contain English words or are \
entirely in English; transcribe those as written.

A person will check your transcription line by line against the scan, so:
- In `lines`, reproduce every handwritten line in order, keeping the writer's own line \
breaks. Do not merge or split lines.
- Correct spelling mistakes (including misspelled Pali/Dhamma terms and wrong tone \
marks), and list every correction in `corrections` with what was actually written. \
Only fix spelling: do not change word choice, grammar, or the writer's style, and do not \
"correct" informal or polite spoken forms such as ค่ะ/คะ/เจ้าค่ะ unless clearly misspelled.
- Wrap every word you cannot read with confidence like ⟦word?⟧, giving your best guess \
inside. Use ⟦?⟧ when you cannot guess at all. Marking a word you were unsure of is much \
better than a confident wrong reading.
- Keep Thai digits as Thai digits and Arabic digits as Arabic digits.
- Skip scanner marks, stamps and printed letterheads that are not part of the writing, \
but mention them in `notes` if they matter.
- In `question`, join the corrected body lines into one paragraph. Do not add anything \
the writer did not say.

You get two images: the full scanned page (for context and layout) and an enlarged crop \
of the handwriting (read from this one). If the crop seems to be missing part of the \
writing, use the full page for that part."""


def image_block(image: Image.Image) -> dict:
    """Turn a PIL image into the content block format the Claude API expects."""
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=90)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/jpeg",
            "data": base64.standard_b64encode(buffer.getvalue()).decode("utf-8"),
        },
    }


def transcribe_page(client: anthropic.Anthropic, doc_dir, page: str) -> dict:
    full_page = Image.open(doc_dir / "pages" / f"{page}.jpg")
    full_page.thumbnail((FULL_PAGE_MAX_SIDE, FULL_PAGE_MAX_SIDE))
    crop = Image.open(doc_dir / "crops" / f"{page}.jpg")

    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": "high"},  # careful reading matters more than speed here
        # If Claude ever declines a page by mistake, the API retries on another model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Full scanned page:"},
                image_block(full_page),
                {"type": "text", "text": "Enlarged crop of the handwriting:"},
                image_block(crop),
                {"type": "text", "text": "Transcribe this page."},
            ],
        }],
        output_format=PageTranscription,
    )

    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"no transcription returned (stop_reason={response.stop_reason})")

    result = response.parsed_output.model_dump()
    # Extra info that helps later: which model read it, and how much it cost in tokens.
    result["_meta"] = {
        "model": response.model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "transcribed_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    return result


def parse_page_numbers(specs: list[str]) -> list[int]:
    """Turn ["3", "7-9"] into [3, 7, 8, 9]."""
    numbers = []
    for spec in specs:
        if "-" in spec:
            start, end = spec.split("-")
            numbers.extend(range(int(start), int(end) + 1))
        else:
            numbers.append(int(spec))
    return numbers


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("document", help="folder name under work/ (the PDF name without .pdf)")
    parser.add_argument("--pages", nargs="+", help="page numbers or ranges, e.g. 3 7-9")
    parser.add_argument("--force", action="store_true", help="redo pages that already have a result")
    args = parser.parse_args()

    doc_dir = work_dir_for(args.document)
    pages = list_pages(doc_dir)
    if not pages:
        raise SystemExit(f"No pages found in {doc_dir}. Run step1_extract_pages.py first.")
    if args.pages:
        pages = [page_name(n) for n in parse_page_numbers(args.pages)]

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    done = failed = 0
    for page in pages:
        out_path = doc_dir / "ai" / f"{page}.json"
        if out_path.exists() and not args.force:
            print(f"  {page}  already done - skipping (use --force to redo)")
            continue
        try:
            result = transcribe_page(client, doc_dir, page)
        except (anthropic.APIError, RuntimeError) as error:
            # One bad page should not stop the whole run; just re-run later for it.
            print(f"  {page}  FAILED: {error}")
            failed += 1
            continue
        write_json(out_path, result)
        done += 1
        print(f"  {page}  {result['confidence']:<6}  {result['lines'][0] if result['lines'] else ''}")

    print(f"\nTranscribed {done} page(s), {failed} failed.")
    if failed:
        print("Run the same command again to retry the failed pages.")
    print("Next: streamlit run step3_review_app.py")


if __name__ == "__main__":
    main()
