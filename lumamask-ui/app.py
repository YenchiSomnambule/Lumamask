import os
import re
import sys

from flask import Flask, request, jsonify, render_template

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lumamask'))

from lumamask.pipeline import run_pipeline

app = Flask(__name__)

MAX_SAMPLES_PER_TYPE = 5

# Conservative residual-PII patterns, run against the MASKED text. Anything
# already tokenised ([AMT_1] etc.) cannot match. Covers the documented
# detector gap (unsigned amounts, see detect.py) plus high-precision formats.
_MISS_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b"),                          # email
    re.compile(r"(?i)(?:\$|\b(?:usd|cad|eur|gbp)\b)\s{0,4}\d[\d,]*(?:\.\d{2})?"),  # currency amount
    re.compile(r"\b\d{1,3}(?:,\d{3})+(?:\.\d{2})?\b"),                        # unsigned grouped amount
    re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),                          # IBAN-like
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                                     # SSN-like
    re.compile(r"\b\d{8,}\b"),                                                # long digit run
]


def count_possible_misses(masked_text: str) -> int:
    """Count non-overlapping spans in *masked_text* that still look sensitive."""
    spans = []
    for pattern in _MISS_PATTERNS:
        for m in pattern.finditer(masked_text):
            spans.append((m.start(), m.end()))
    spans.sort()
    merged = 0
    last_end = -1
    for start, end in spans:
        if start >= last_end:
            merged += 1
            last_end = end
        else:
            last_end = max(last_end, end)
    return merged


def summarise_detections(pmap: dict) -> tuple[dict, dict]:
    """
    Build the Detected-tab data from the placeholder map, without sending
    the map itself (token ↔ value pairs) to the frontend.

    Returns ({entity_type: distinct_count}, {entity_type: [sample values]}).
    """
    counts: dict[str, int] = {}
    samples: dict[str, list[str]] = {}
    for entry in pmap.get('entries', []):
        et = entry['entity_type']
        counts[et] = counts.get(et, 0) + 1
        bucket = samples.setdefault(et, [])
        if len(bucket) < MAX_SAMPLES_PER_TYPE:
            bucket.append(entry['real_value'])
    return counts, samples


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/run', methods=['POST'])
def run():
    data = request.get_json(silent=True) or {}
    api_key = (data.get('api_key') or '').strip()
    text = (data.get('text') or '').strip()
    instruction = (data.get('instruction') or '').strip()

    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    if not text:
        return jsonify({'error': 'Document text is required'}), 400
    if not instruction:
        return jsonify({'error': 'Instruction is required'}), 400

    previous_key = os.environ.get('ANTHROPIC_API_KEY')
    os.environ['ANTHROPIC_API_KEY'] = api_key
    try:
        result = run_pipeline(text, instruction)
        counts, samples = summarise_detections(result['map'])

        return jsonify({
            'detection_summary': counts,
            'detection_samples': samples,
            'possible_misses': count_possible_misses(result['masked']),
            'masked': result['masked'],
            'ai_reply_masked': result['ai_reply_tokenised'],
            'final_answer': result['ai_reply_restored'],
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    finally:
        if previous_key is None:
            os.environ.pop('ANTHROPIC_API_KEY', None)
        else:
            os.environ['ANTHROPIC_API_KEY'] = previous_key


# Startup is handled by entry.py (for the .exe) or run_ui.bat (for dev).
# Do not add a __main__ block here.
