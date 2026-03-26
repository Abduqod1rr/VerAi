from flask import Flask, request, jsonify, send_from_directory
import requests
import json
import os

app = Flask(__name__, static_folder='public')

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')  # set this in Render environment variables

@app.route('/')
def index():
    return send_from_directory('public', 'index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.get_json()
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {GROQ_API_KEY}'
            },
            json={
                'model': 'llama-3.3-70b-versatile',
                'max_tokens': 1000,
                'messages': [
                    {
                        'role': 'system',
                        'content': """You are a fake news detection expert. Analyze the given news text and return ONLY a valid JSON object. No preamble, no markdown, no backticks. Write summary and signals in Uzbek language. Use exactly these fields: {"verdict": "LIKELY FAKE" or "SUSPICIOUS" or "LIKELY REAL", "confidence": integer 0-100, "summary": "2-3 jumladan iborat tushuntirish o'zbek tilida", "signals": ["3 dan 5 tagacha qisqa signal o'zbek tilida"]}"""
                    },
                    {
                        'role': 'user',
                        'content': text
                    }
                ]
            }
        )

        if not response.ok:
            err = response.json()
            return jsonify({'error': err.get('error', {}).get('message', 'Groq API error')}), 500

        result = response.json()
        raw = result['choices'][0]['message']['content']
        clean = raw.replace('```json', '').replace('```', '').strip()
        parsed = json.loads(clean)
        return jsonify(parsed)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 3000))
    app.run(host='0.0.0.0', port=port)