# Thai handwriting → text (with human review)

Turns scanned PDFs of handwritten Thai (and English) question slips into checked text.
Claude reads the handwriting; a person checks each page using plain text files.

This folder is separate from the FarmDeApp website code; nothing here touches the site.

> **Privacy:** `input/`, `work/` and `api_key.txt` hold private letters and your key.
> They are in `.gitignore` and are never pushed to GitHub. Keep your own backup of `work/`.

---

## Install (Linux / Chromebook)

```bash
curl -fsSLO https://raw.githubusercontent.com/apinyacode/FarmDeApp/claude/quirky-sagan-27izb0/thai_ocr/deploy.sh
bash deploy.sh
cd ~/thai_ocr
```

`bash ~/thai_ocr/deploy.sh` reinstalls fresh any time (stops anything running, deletes the old
scripts, downloads new ones). Your `work/`, `input/` and `api_key.txt` are kept.
`--wipe-data` also starts with no data (old data is moved to `~/thai_ocr_backup_<date>`).

---

## 1. Transcribe

Copy your PDF into `~/thai_ocr/input/` with a simple name (no spaces or Thai letters), then:

```bash
./ocr.sh transcribe input/batch_68_1.pdf --pages 1-3   # try 3 pages first
./ocr.sh transcribe input/batch_68_1.pdf               # then everything (done pages are skipped)
```

The first run asks for your API key once. Cost is about **US$0.06 per page**.

## 2. Review

Open `~/thai_ocr/work/batch_68_1/review/` in the Files app. Every page has two files:

| File | What it is |
|---|---|
| `page_001.jpg` | the handwriting |
| `page_001_REVIEW.txt` | Claude's text, **not checked yet** |
| `page_001_DONE.txt` | the same file after you checked it and **renamed** it |

For each page:
1. Open the `.jpg` and the `.txt` side by side.
2. Fix the text. Words Claude wasn't sure of look like `⟦word?⟧`: check them and remove the `⟦ ⟧`.
3. Save, then **rename** the file from `_REVIEW.txt` to `_DONE.txt`.

Each text file has four parts:

```
== TEXT (same line breaks as the paper) ==        line by line, spelling corrected
== CLEAN VERSION (one paragraph) ==                the whole question as one paragraph
== SPELLING FIXES (as written -> corrected) ==     what Claude corrected, e.g. line 12: ได -> ได้
== NOTES ==                                        anything odd: crossings-out, underlines, ...
```

Lines starting with `#` at the top are just help (confidence, number of unsure words) and are ignored.

See how far you are:

```bash
./ocr.sh status
```

## 3. Export

```bash
./ocr.sh export input/batch_68_1.pdf              # all pages, with REVIEW / DONE status
./ocr.sh export input/batch_68_1.pdf --done-only  # only pages you renamed to _DONE
```

In `work/batch_68_1/export/` you get a **.csv** (opens in Excel / Google Sheets) and a
**.docx** with each scan next to its text. Export as often as you like.

---

## Good to know

- **Re-running is safe.** `transcribe` never overwrites a `.txt` file, so your corrections are
  never lost. To get Claude's text again for a page, delete that page's `.txt` and run `transcribe`.
- **Redo a page with Claude** (costs again): `./ocr.sh transcribe input/x.pdf --pages 17 --force`,
  then delete the old `page_017_*.txt` to get the new text.
- **Wrong API key?** Delete `api_key.txt` and run again.
- **Claude keeps misreading a word or name?** Add it to the vocabulary examples in
  `SYSTEM_PROMPT` at the top of `step2_transcribe.py`.

## Files

| File | What it does |
|---|---|
| `ocr.sh` | the three commands above |
| `deploy.sh` | fresh install / update |
| `step1_extract_pages.py` | PDF → page images + cropped handwriting |
| `step2_transcribe.py` | sends each page to Claude, writes the `_REVIEW.txt` files |
| `step3_export.py` | text files → CSV + Word |
| `common.py` | shared code: folders, the text-file format |

You can also run the Python steps directly, e.g.
`.venv/bin/python step2_transcribe.py batch_68_1 --pages 5`.
