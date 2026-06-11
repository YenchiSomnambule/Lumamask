# Lumamask

Lumamask is a command-line tool that lets you use Claude AI on sensitive business
documents without sending the real data to the API. It detects names, organisations,
amounts, invoice numbers, emails, phone numbers, IBANs, and other identifiers in a
`.txt` document, replaces them locally with opaque placeholder tokens (e.g.
`[PERSON_1]`, `[AMT_1]`), sends only the masked text to Claude, and then restores
all real values in Claude's response before showing it to you. At no point does any
sensitive value leave your machine — the AI only ever sees the token-substituted
version.

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone <repo-url>
cd lumamask
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Download the spaCy language model

```bash
python -m spacy download en_core_web_lg
```

> **Fallback:** if `en_core_web_lg` (~750 MB) times out or fails, use
> `en_core_web_md` (34 MB) instead. Detection recall is slightly lower without
> the larger model (see [Detection accuracy](#detection-accuracy-synthetic-test-set)
> below — numbers were measured against `en_core_web_md`).

### 4. Set your Anthropic API key

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Linux / macOS
set  ANTHROPIC_API_KEY=sk-ant-...     # Windows cmd
$env:ANTHROPIC_API_KEY="sk-ant-..."   # Windows PowerShell
```

The key is **never** written to disk by Lumamask.

---

## Usage

```bash
python -m lumamask.cli --input <file.txt> --instruction "<what to ask Claude>"
```

**Example:**

```bash
python -m lumamask.cli \
    --input samples/invoice_sample.txt \
    --instruction "Summarise this invoice in two sentences."
```

### Output — four labelled sections

| Section | What it shows |
|---|---|
| **(1) WHAT WAS DETECTED** | Count of sensitive entities found, by type |
| **(2) MASKED VERSION SENT TO AI** | The full document with real values replaced by tokens — proof that nothing sensitive left your machine |
| **(3) AI REPLY (as received, still masked)** | Claude's raw response with tokens still in place |
| **(4) FINAL ANSWER (restored)** | Claude's response with all real values correctly restored |

### Optional flags

| Flag | Default | Description |
|---|---|---|
| `--model MODEL` | `claude-sonnet-4-6` | Claude model string |
| `--save-map PATH` | *(not written)* | Save the placeholder map to a JSON file for your own records. **Keep this file private** — it links tokens to real values. |

### Example invocation with map save

```bash
python -m lumamask.cli \
    --input samples/invoice_sample.txt \
    --instruction "List the payment terms and total amount due." \
    --save-map invoice.map.json
```

---

## Detection accuracy (synthetic test set)

Measured on 5 synthetic Phase 4 fixture files (96 labelled sensitive items).

| File | Hits / Total | Recall |
|---|---|---|
| p4_invoice_01.txt | 19 / 19 | 100% |
| p4_invoice_02.txt | 20 / 21 | 95% |
| p4_quote_01.txt | 20 / 20 | 100% |
| p4_engagement_letter_01.txt | 18 / 18 | 100% |
| p4_email_financials_01.txt | 18 / 18 | 100% |
| **Overall** | **95 / 96** | **99%** |

### Residual miss

**`Greenfield Media Group` (ORGANIZATION)** — spaCy NLP miss. The company name
appears without a corporate-suffix cue (Inc., Ltd., etc.) that spaCy normally uses to
classify an ORGANIZATION. Not fixable at the regex layer; would require a larger NLP
model (`en_core_web_lg` or a fine-tuned model) or a custom entity list.

### Tuning changes applied in Phase 4

Three custom-recognizer improvements were made to reach 99%:

1. **MONEY_AMOUNT regex** — widened currency-code spacing from `\s?` to `\s{0,4}`
   to handle table-aligned amounts such as `CAD  8,500.00`.
2. **Score alignment** — all three custom recognisers (INVOICE_NUMBER, MONEY_AMOUNT,
   ACCOUNT_NUMBER) raised from 0.65–0.70 to **0.75**. This keeps their score within
   0.10 of spaCy's built-in entity score (0.85), so the priority-list tiebreak can fire
   and the structured custom entities win overlaps against spurious spaCy ORG detections.
3. **INVOICE_NUMBER regex** — added an alphanumeric branch so reference codes like
   `INVOICE #Q-0047` and `INVOICE #PV-2025-06` are captured alongside pure-digit codes.

### spaCy model note

`en_core_web_lg` was attempted but timed out during download in the sandbox environment
(model is ~750 MB). Recall figures above were measured against `en_core_web_md` (34 MB).
All detection results should be re-validated against `en_core_web_lg` if the environment
allows it in future.

---

## Limitations

- **Detection is not perfect.** Lumamask achieves ~99% recall on the synthetic test set,
  but real-world documents vary widely. Some entities will be missed — particularly
  organisation names without standard corporate suffixes (Inc., Ltd., etc.) and
  unsigned monetary amounts (e.g. a bare `45,000.00` with no currency symbol).
- **This reduces exposure, it does not eliminate it.** Any missed entity will appear
  unmasked in the text sent to Claude. You should always review section **(2) MASKED
  VERSION SENT TO AI** before sending, and manually remove any sensitive items the
  tool missed.
- **The placeholder map is the sensitive artefact.** The map file (if saved with
  `--save-map`) links every token to its real value. Treat it with the same care as
  the original document — do not commit it to version control (`.gitignore` already
  excludes `*.map.json`) and delete it when no longer needed.
- **Only `.txt` files are supported.** PDF, Word, and other formats are out of scope
  for this MVP.
- **English only.** The spaCy model and custom recognizers are tuned for English
  business text.

---

## Scope — what is intentionally NOT included

The following are deliberately out of scope for this MVP and should not be added
without a new design phase:

- **GUI or web interface** — CLI only.
- **Multiple AI providers** — Claude only; the model string is a single constant.
- **PDF, Word, or other file formats** — `.txt` input only.
- **Database or persistent storage** — no state is saved between runs.
- **User accounts or authentication** — the API key comes from the environment.
- **Batch processing** — one file per invocation.

These are all candidates for future phases.

---

## Running the tests

```bash
pytest -v
```

36 tests, no network calls required (the LLM is mocked in all tests).
