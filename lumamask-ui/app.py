import os
import sys

from flask import Flask, request, jsonify, render_template

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'lumamask'))

from lumamask.pipeline import run_pipeline
from lumamask.detect import detect

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/run', methods=['POST'])
def run():
    data = request.json
    api_key = data.get('api_key', '').strip()
    text = data.get('text', '').strip()
    instruction = data.get('instruction', '').strip()

    if not api_key:
        return jsonify({'error': 'API key is required'}), 400
    if not text:
        return jsonify({'error': 'Document text is required'}), 400
    if not instruction:
        return jsonify({'error': 'Instruction is required'}), 400

    os.environ['ANTHROPIC_API_KEY'] = api_key
    try:
        result = run_pipeline(text, instruction)
        detections = detect(text)
        counts = {}
        for d in detections:
            et = d['entity_type']
            counts[et] = counts.get(et, 0) + 1

        return jsonify({
            'detection_summary': counts,
            'masked': result['masked'],
            'ai_reply_masked': result['ai_reply_tokenised'],
            'final_answer': result['ai_reply_restored'],
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except RuntimeError as e:
        return jsonify({'error': str(e)}), 502
    finally:
        os.environ.pop('ANTHROPIC_API_KEY', None)


if __name__ == '__main__':
    import webbrowser
    import threading
    threading.Timer(1.2, lambda: webbrowser.open('http://localhost:5000')).start()
    app.run(debug=False, port=5000)
