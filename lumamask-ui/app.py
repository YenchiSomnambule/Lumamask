import os
import re
import socket
import sys
import threading
import traceback

from flask import Flask, request, jsonify, render_template

import extract
from extract import ExtractionError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lumamask'))

# The detection pipeline pulls in presidio + spaCy — heavy, and only needed
# once the user clicks Run. Keep this import resilient so the web server, the
# page itself, and the file-upload/extract endpoint still come up when the NLP
# stack isn't installed; /api/run then reports the missing engine clearly
# instead of the whole app failing to import.
try:
    from lumamask.pipeline import run_pipeline
except Exception:  # pragma: no cover - depends on the runtime environment
    run_pipeline = None

app = Flask(__name__)
# Reject oversized uploads at the WSGI layer (a little headroom over the
# per-file cap for multipart framing); the 413 handler renders it as JSON.
app.config['MAX_CONTENT_LENGTH'] = extract.MAX_UPLOAD_BYTES + (1 * 1024 * 1024)

MAX_SAMPLES_PER_TYPE = 5
DEFAULT_PORT = 5000

# The Flask dev server is threaded; ANTHROPIC_API_KEY lives in process-global
# os.environ, so concurrent /api/run requests must not interleave.
_pipeline_lock = threading.Lock()

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


def find_available_port(preferred: int = DEFAULT_PORT) -> int:
    """Return *preferred* if free, else an OS-assigned free port.

    Binding to an already-used port would make the window/browser show
    whatever foreign app owns it — always verify before serving.
    """
    for candidate in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('127.0.0.1', candidate))
                return s.getsockname()[1]
        except OSError:
            continue
    raise RuntimeError('No free TCP port available on 127.0.0.1')


def _prewarm() -> None:
    """Load the spaCy model so the first /api/run doesn't pay the 3-5s cost."""
    try:
        from lumamask.detect import _get_analyzer
        _get_analyzer()
    except Exception:
        # Best-effort only; a failure here will resurface on the first request
        # with a proper error message.
        pass


def start_prewarm_thread() -> threading.Thread:
    t = threading.Thread(target=_prewarm, daemon=True)
    t.start()
    return t


@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(413)
def _too_large(_err):
    """Render Flask's oversized-upload rejection as JSON, not an HTML page."""
    mb = extract.MAX_UPLOAD_BYTES // (1024 * 1024)
    return jsonify({'error': f'File is too large (limit {mb} MB).'}), 413


@app.route('/api/extract', methods=['POST'])
def api_extract():
    """Extract plain text from a single uploaded document file.

    The bytes are parsed in-process and only the resulting text is returned —
    nothing is written to disk, and the detection/LLM pipeline is not involved
    here. The text lands in the document box; the user reviews it and then
    clicks Run, which goes through /api/run exactly as pasted text would.
    """
    uploaded = request.files.get('file')
    if uploaded is None or not uploaded.filename:
        return jsonify({'error': 'No file uploaded.'}), 400

    try:
        text = extract.extract_text(uploaded.filename, uploaded.read())
    except ExtractionError as e:
        # Expected, user-actionable failures (bad format, corrupt file, etc.)
        return jsonify({'error': str(e)}), 400
    except Exception:
        # Never leak a raw traceback to the client.
        traceback.print_exc()
        return jsonify({'error': 'Could not read the uploaded file.'}), 500

    return jsonify({'text': text, 'filename': uploaded.filename})


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

    with _pipeline_lock:
        if run_pipeline is None:
            return jsonify({
                'error': 'Detection engine is unavailable — the server is '
                         'missing its NLP dependencies (presidio / spaCy).'
            }), 500
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
        except Exception:
            # Never leak a raw HTML 500 (or the API key) to the client.
            traceback.print_exc()
            return jsonify({'error': 'Internal server error — see server log.'}), 500
        finally:
            if previous_key is None:
                os.environ.pop('ANTHROPIC_API_KEY', None)
            else:
                os.environ['ANTHROPIC_API_KEY'] = previous_key


if __name__ == '__main__':
    # Dev mode (run_ui.bat): serve in a browser tab.
    # The packaged exe uses entry.py instead, which imports this module.
    import webbrowser
    port = find_available_port()
    start_prewarm_thread()
    threading.Timer(1.2, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    app.run(host='127.0.0.1', port=port, debug=False)
