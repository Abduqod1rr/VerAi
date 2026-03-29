from flask import Flask, request, jsonify, send_from_directory, session, redirect
from functools import wraps
import requests
import json
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

app = Flask(__name__, static_folder='public')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-me')

# Supabase setup
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')  # set this in Render environment variables


# ── Auth decorator ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'access_token' not in session:
            return jsonify({'error': 'Avtorizatsiya talab qilinadi'}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    return send_from_directory('public', 'index.html')


@app.route('/auth')
def auth_page():
    return send_from_directory('public', 'auth.html')


# ── Auth API ────────────────────────────────────────────────────
@app.route('/api/register', methods=['POST'])
def register():
    if not supabase:
        return jsonify({'error': 'Supabase sozlanmagan'}), 500

    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'error': 'Email va parol kiritilishi shart'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Parol kamida 6 ta belgidan iborat bo\'lishi kerak'}), 400

    try:
        res = supabase.auth.sign_up({
            'email': email,
            'password': password
        })

        if res.user:
            # If email confirmation is disabled, we get a session immediately
            if res.session:
                session['access_token'] = res.session.access_token
                session['refresh_token'] = res.session.refresh_token
                session['user_email'] = res.user.email
                session['user_id'] = res.user.id
                return jsonify({
                    'message': 'Muvaffaqiyatli ro\'yxatdan o\'tdingiz!',
                    'user': {'email': res.user.email, 'id': res.user.id}
                }), 201
            else:
                # Email confirmation is enabled
                return jsonify({
                    'message': 'Ro\'yxatdan o\'tdingiz! Emailingizni tasdiqlang.',
                    'needs_confirmation': True
                }), 201
        else:
            return jsonify({'error': 'Ro\'yxatdan o\'tishda xatolik yuz berdi'}), 400

    except Exception as e:
        error_msg = str(e)
        if 'already registered' in error_msg.lower() or 'already been registered' in error_msg.lower():
            return jsonify({'error': 'Bu email allaqachon ro\'yxatdan o\'tgan'}), 409
        return jsonify({'error': f'Xatolik: {error_msg}'}), 400


@app.route('/api/login', methods=['POST'])
def login():
    if not supabase:
        return jsonify({'error': 'Supabase sozlanmagan'}), 500

    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'error': 'Email va parol kiritilishi shart'}), 400

    try:
        res = supabase.auth.sign_in_with_password({
            'email': email,
            'password': password
        })

        session['access_token'] = res.session.access_token
        session['refresh_token'] = res.session.refresh_token
        session['user_email'] = res.user.email
        session['user_id'] = res.user.id

        return jsonify({
            'message': 'Muvaffaqiyatli kirdingiz!',
            'user': {'email': res.user.email, 'id': res.user.id}
        }), 200

    except Exception as e:
        error_msg = str(e)
        if 'invalid' in error_msg.lower() or 'credentials' in error_msg.lower():
            return jsonify({'error': 'Email yoki parol noto\'g\'ri'}), 401
        return jsonify({'error': f'Xatolik: {error_msg}'}), 400


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'message': 'Chiqdingiz'}), 200


@app.route('/api/me', methods=['GET'])
def me():
    if 'access_token' not in session:
        return jsonify({'authenticated': False}), 401
    return jsonify({
        'authenticated': True,
        'user': {
            'email': session.get('user_email'),
            'id': session.get('user_id')
        }
    }), 200


# ── Analyze (protected) ────────────────────────────────────────
@app.route('/analyze', methods=['POST'])
@login_required
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