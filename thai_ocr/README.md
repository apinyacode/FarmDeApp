# Thai handwriting → text (with human review)

Turns scanned PDFs of handwritten Thai into checked, searchable text.
Claude reads the handwriting, and a person checks every page side by side with the scan.

```
PDF ─► step 1: split + crop ─► step 2: Claude reads ─► step 3: human review ─► step 4: export
        work/<name>/pages/      work/<name>/ai/          work/<name>/reviewed/    work/<name>/export/
        work/<name>/crops/                                                         (.csv + .docx)
```

This folder is separate from the FarmDeApp website code; nothing here touches the site.

> **Privacy:** `input/` and `work/` hold the scans and transcriptions. They are in
> `.gitignore` so private letters are never pushed to GitHub. Keep your own backup of `work/`.

---

## The simple way (Linux / Mac)

**Download** (creates a `thai_ocr` folder where you are):

```bash
curl -L https://github.com/apinyacode/FarmDeApp/archive/refs/heads/claude/quirky-sagan-27izb0.tar.gz | tar xz --strip-components=1 --wildcards '*/thai_ocr'
cd thai_ocr
```

**Run** (the first run installs everything and asks for your API key once):

```bash
./ocr.sh transcribe ~/questions_2560.pdf --pages 1-3   # try 3 pages first
./ocr.sh transcribe ~/questions_2560.pdf               # then all pages (done pages are skipped)
./ocr.sh review                                        # open http://localhost:8501
./ocr.sh export ~/questions_2560.pdf                   # CSV + Word in work/questions_2560/export/
```

Wrong API key? Delete `api_key.txt` and run again. The sections below explain each step
in detail and how to run the Python scripts directly (e.g. on Windows).

## Manual setup (Windows, or if you prefer)

1. **Install Python 3.10 or newer** (you probably already have it: `python --version`).
2. Open a terminal **in this `thai_ocr` folder** and create a virtual environment:

   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # Mac / Linux:
   source .venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Get an Anthropic API key** at https://console.anthropic.com → *API keys*, then set it
   in the same terminal (you need to do this each time you open a new terminal):

   ```bash
   # Windows (Command Prompt)
   set ANTHROPIC_API_KEY=sk-ant-...
   # Windows (PowerShell)
   $env:ANTHROPIC_API_KEY="sk-ant-..."
   # Mac / Linux
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

---

## Running it

Put your PDF in `input/` (create the folder if needed). Use a simple file name without
spaces, e.g. `input/questions_2560.pdf`. The name without `.pdf` becomes the document name.

### Step 1: split into pages and crop

```bash
python step1_extract_pages.py input/questions_2560.pdf
```

Open a few images in `work/questions_2560/crops/` to check that each one shows the whole
slip. If writing gets cut off, adjust the numbers at the top of `step1_extract_pages.py`.
Claude also sees the full page, so a slightly bad crop is not a disaster.

### Step 2: Claude transcribes

**Try 3 pages first** so you can see the quality and the cost before doing all of them:

```bash
python step2_transcribe.py questions_2560 --pages 1-3
```

Then run the rest (pages already done are skipped automatically):

```bash
python step2_transcribe.py questions_2560
```

- To redo one page: `python step2_transcribe.py questions_2560 --pages 17 --force`
- Each result has `_meta.input_tokens` / `output_tokens`, so you can see the real cost.
  Expect very roughly **US$0.05–0.10 per page** with Claude Opus 5.5.
- If a page fails (network, rate limit), just run the same command again.

### Step 3: review in the browser

```bash
streamlit run step3_review_app.py
```

Your browser opens at http://localhost:8501.

- **Left:** the scan. Hover over it and click ⛶ for full screen; the *Full page* tab shows the whole sheet.
- **Right:** a numbered line-by-line preview. **Yellow** = Claude was unsure of the word.
  **Green underline** = a spelling mistake Claude corrected; hover over it to see how it was written.
  Below that are the editable boxes and the *Spelling fixes* table.
- If a "fix" is wrong (the writer was right, or Claude misread), change the word back in the
  lines box and delete that row from the *Spelling fixes* table.
- Fix the text, remove the `⟦ ⟧` marks around words you have checked, then press **✅ Approve**.
  **💾 Later** saves your edits but keeps the page in the "not approved" list.
- The sidebar filter *Low/medium confidence first* lets you start with the hardest pages.
- Several people can split the work: type your name in the sidebar and it's saved with each review.

Your edits go to `reviewed/`. Claude's original stays untouched in `ai/`, so re-running
step 2 never overwrites human work.

### Step 4: export

```bash
python step4_export.py questions_2560                 # everything (approved + not yet reviewed)
python step4_export.py questions_2560 --approved-only # only checked pages
```

You get, in `work/questions_2560/export/`:
- a **.csv** (opens in Excel / Google Sheets with Thai shown correctly), one row per page
- a **.docx** with each scan next to its transcription, for printing or a final read-through

---

## What each field means

| Field | Meaning |
|---|---|
| `lines` | The text line by line, same line breaks as the paper, **spelling corrected**. `⟦word?⟧` = Claude unsure. |
| `corrections` | Every spelling fix: line number, what was written, what it was corrected to. |
| `greeting` / `closing` | The opening salutation and the thanks at the end. |
| `question` | The corrected body lines joined into one paragraph (no greeting/closing). |
| `continues_from_previous` / `continues_to_next` | For questions that run over 2+ pages (e.g. pages marked ① ②). |
| `notes` | Underlines, crossings-out, English words, anything odd. |
| `confidence` | Claude's own rating: high / medium / low. |
| `status` | `approved`, `needs_check` (saved for later), or `ai_only` (nobody has looked yet). |

## Files

| File | What it does |
|---|---|
| `common.py` | Folder layout, the data shape Claude must return, small helpers |
| `step1_extract_pages.py` | PDF → page images + cropped handwriting |
| `step2_transcribe.py` | Sends each page to Claude, saves JSON. The prompt is `SYSTEM_PROMPT` at the top. |
| `step3_review_app.py` | Streamlit review app |
| `step4_export.py` | CSV + Word export |

**Tuning accuracy:** if Claude keeps getting a particular word or name wrong, add it to the
vocabulary examples in `SYSTEM_PROMPT` in `step2_transcribe.py` and re-run those pages with `--force`.
