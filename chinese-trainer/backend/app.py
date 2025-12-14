from flask import Flask, jsonify, request, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import json
import random
import os
import uuid
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Секретный ключ для сессий
app.permanent_session_lifetime = timedelta(days=7)  # Сессия на 7 дней
CORS(app, supports_credentials=True)

# Пути к файлам
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DICTIONARY_PATH = os.path.join(BASE_DIR, '../data/dictionary.json')
USER_WORDS_PATH = os.path.join(BASE_DIR, '../data/user_words.json')
USERS_PATH = os.path.join(BASE_DIR, '../data/users.json')

def ensure_file_exists(filepath, default_content='[]'):
    """Создает файл, если его нет"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(default_content)

def load_users():
    """Загружает пользователей"""
    ensure_file_exists(USERS_PATH)
    try:
        with open(USERS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки пользователей: {e}")
        return []

def save_users(users):
    """Сохраняет пользователей"""
    ensure_file_exists(USERS_PATH)
    try:
        with open(USERS_PATH, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения пользователей: {e}")
        return False

def get_current_user():
    """Получает текущего пользователя"""
  user_id = session.get('user_id')
    if user_id:
        users = load_users()
        return next((u for u in users if u['id'] == user_id), None)
    return None

# Загружаем словари
def load_dictionary():
    """Загружает основной словарь"""
    ensure_file_exists(DICTIONARY_PATH)
    try:
        with open(DICTIONARY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Ошибка загрузки словаря: {e}")
        return []

def load_user_words(user_id=None):
    """Загружает пользовательские слова"""
    ensure_file_exists(USER_WORDS_PATH)
    try:
        with open(USER_WORDS_PATH, 'r', encoding='utf-8') as f:
            all_user_words = json.load(f)

        if user_id:
            # Возвращаем только слова текущего пользователя
            return [w for w in all_user_words if w.get('user_id') == user_id]
        return all_user_words
    except Exception as e:
        print(f"Ошибка загрузки пользовательских слов: {e}")
        return []

def save_user_words(words):
    """Сохраняет пользовательские слова"""
    ensure_file_exists(USER_WORDS_PATH)
    try:
        with open(USER_WORDS_PATH, 'w', encoding='utf-8') as f:
            json.dump(words, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Ошибка сохранения пользовательских слов: {e}")
        return False

def get_all_words(user_id=None):
    """Возвращает все слова (основные + пользовательские)"""
    main_words = load_dictionary()
    
    if user_id:
        user_words = load_user_words(user_id)
      else:
        user_words = load_user_words()
    
    # Добавляем флаг, что это пользовательские слова
    for word in user_words:
        word['isUserWord'] = True
        word['id'] = f"user_{word.get('id', hash(str(word)))}"
    
    return main_words + user_words

# ========== АВТОРИЗАЦИЯ ==========

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных'}), 400

        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()

        if not username or not password:
            return jsonify({'error': 'Имя пользователя и пароль обязательны'}), 400

        if len(username) < 3:
            return jsonify({'error': 'Имя пользователя должно быть не менее 3 символов'}), 400

        if len(password) < 6:
            return jsonify({'error': 'Пароль должен быть не менее 6 символов'}), 400

        users = load_users()

        # Проверяем, существует ли пользователь
        if any(u['username'] == username for u in users):
            return jsonify({'error': 'Пользователь с таким именем уже существует'}), 400

        # Создаем нового пользователя
        new_user = {
            'id': str(uuid.uuid4()),
            'username': username,
            'password_hash': generate_password_hash(password),
            'email': email,
            'created_at': int(os.path.time() * 1000),
            'stats': {
                'words_added': 0,
                'games_played': 0,
                'correct_answers': 0,
                'total_answers': 0
                 }
        }

        users.append(new_user)

        if save_users(users):
            # Автоматически логиним пользователя
            session.permanent = True
            session['user_id'] = new_user['id']

            return jsonify({
                'success': True,
                'message': 'Регистрация успешна',
                'user': {
                    'id': new_user['id'],
                    'username': new_user['username'],
                    'email': new_user['email'],
                    'stats': new_user['stats']
                }
            }), 201
        else:
            return jsonify({'error': 'Ошибка сохранения пользователя'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных'}), 400

        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({'error': 'Имя пользователя и пароль обязательны'}), 400

        users = load_users()
        user = next((u for u in users if u['username'] == username), None)

        if not user:
            return jsonify({'error': 'Пользователь не найден'}), 404

        if not check_password_hash(user['password_hash'], password):
            return jsonify({'error': 'Неверный пароль'}), 401

        # Устанавливаем сессию
        session.permanent = True
      session['user_id'] = user['id']

        return jsonify({
            'success': True,
            'message': 'Вход выполнен успешно',
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'stats': user['stats']
            }
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'success': True, 'message': 'Выход выполнен'})

@app.route('/api/auth/check', methods=['GET'])
def check_auth():
    user = get_current_user()
    if user:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'stats': user['stats']
            }
        })
    return jsonify({'authenticated': False})

@app.route('/api/auth/stats', methods=['GET'])
def get_stats():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Не авторизован'}), 401
    
    return jsonify({
        'success': True,
        'stats': user['stats']
    })

@app.route('/api/auth/stats/update', methods=['POST'])
def update_stats():
    user = get_current_user()
if not user:
        return jsonify({'error': 'Не авторизован'}), 401
    
    try:
        data = request.get_json()
        stat_type = data.get('type')
        value = data.get('value', 1)

        users = load_users()
        user_index = next((i for i, u in enumerate(users) if u['id'] == user['id']), -1)

        if user_index >= 0 and stat_type in users[user_index]['stats']:
            users[user_index]['stats'][stat_type] += value
            save_users(users)

            return jsonify({
                'success': True,
                'stats': users[user_index]['stats']
            })
        else:
            return jsonify({'error': 'Некорректный тип статистики'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== ОСНОВНОЙ ФУНКЦИОНАЛ ==========

@app.route('/')
def home():
    return "Chinese Trainer API is running!"

# Получить все слова (для авторизованных пользователей - только их слова)
@app.route('/api/words', methods=['GET'])
def get_words():
    try:
        user = get_current_user()
        user_id = user['id'] if user else None
        words = get_all_words(user_id)
        return jsonify(words)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Добавить новое слово
@app.route('/api/words', methods=['POST'])
def add_word():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Не авторизован'}), 401
          
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных'}), 400

        # Проверяем обязательные поля
        required_fields = ['simplified', 'pinyin', 'translation']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return jsonify({'error': f'Поле {field} обязательно'}), 400

        # Создаем новое слово
        new_word = {
            'id': str(int(os.time() * 1000)),  # Простой ID на основе времени
            'user_id': user['id'],
            'simplified': str(data['simplified']).strip(),
            'pinyin': str(data['pinyin']).strip(),
            'translation': str(data['translation']).strip(),
            'example': str(data.get('example', '')).strip(),
            'example_translation': str(data.get('example_translation', '')).strip(),
            'created_at': int(os.time() * 1000)
        }

        # Загружаем существующие слова
        user_words = load_user_words()
        user_words.append(new_word)

        # Сохраняем
        if save_user_words(user_words):
            # Обновляем статистику пользователя
            update_stats_data = {'type': 'words_added', 'value': 1}
            request._cached_data = json.dumps(update_stats_data)
            update_stats()

            return jsonify({
                'success': True,
                'message': 'Слово добавлено',
                'word': new_word
            }), 201
        else:
            return jsonify({'error': 'Ошибка сохранения'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Удалить слово
@app.route('/api/words/<word_id>', methods=['DELETE'])
def delete_word(word_id):
    try:
        user = get_current_user()
if not user:
            return jsonify({'error': 'Не авторизован'}), 401

        user_words = load_user_words()

        # Удаляем префикс 'user_' для поиска
        search_id = word_id.replace('user_', '')

        # Ищем слово для удаления (только свое)
        initial_count = len(user_words)
        user_words = [
            word for word in user_words 
            if str(word.get('id', '')) != search_id or word.get('user_id') != user['id']
        ]

        if len(user_words) == initial_count:
            return jsonify({'error': 'Слово не найдено'}), 404

        # Сохраняем обновленный список
        if save_user_words(user_words):
            return jsonify({'success': True, 'message': 'Слово удалено'})
        else:
            return jsonify({'error': 'Ошибка сохранения'}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Получить слова для тренировки
@app.route('/api/practice', methods=['POST'])
def get_practice_words():
    try:
        user = get_current_user()
        user_id = user['id'] if user else None

        data = request.get_json() or {}
        word_ids = data.get('word_ids', [])

        all_words = get_all_words(user_id)

        if word_ids:
            # Фильтруем по выбранным ID
            selected_words = [w for w in all_words if w['id'] in word_ids]
        else:
            # Если не выбрано - берем 5 случайных
            selected_words = random.sample(all_words, min(5, len(all_words)))

        # Перемешиваем
        random.shuffle(selected_words)
        return jsonify(selected_words)
    except Exception as e:
 return jsonify({'error': str(e)}), 500

# Проверить ответ
@app.route('/api/check', methods=['POST'])
def check_answer():
    try:
        user = get_current_user()

        data = request.get_json()
        if not data:
            return jsonify({'error': 'Нет данных'}), 400

        word_id = data.get('word_id')
        user_answer = data.get('answer', '').strip().lower()

        user_id = user['id'] if user else None
        all_words = get_all_words(user_id)

        word = next((w for w in all_words if str(w.get('id')) == str(word_id)), None)

        if not word:
            return jsonify({'error': 'Word not found'}), 404

        # Сравниваем ответы (игнорируем пробелы и регистр)
        correct_answer = word['pinyin'].lower().replace(' ', '')
        user_answer_clean = user_answer.replace(' ', '')

        is_correct = user_answer_clean == correct_answer

        # Обновляем статистику пользователя
        if user and is_correct:
            update_stats_data = {'type': 'correct_answers', 'value': 1}
            request._cached_data = json.dumps(update_stats_data)
            update_stats()

        if user:
            update_stats_data = {'type': 'total_answers', 'value': 1}
            request._cached_data = json.dumps(update_stats_data)
            update_stats()

        return jsonify({
            'correct': is_correct,
            'correct_answer': word['pinyin'],
            'word': word['simplified'],
            'translation': word['translation'],
            'example': word.get('example', ''),
            'example_translation': word.get('example_translation', ''),
            'isUserWord': word.get('isUserWord', False)
        })
    except Exception as e:
      return jsonify({'error': str(e)}), 500

# Завершить игру и обновить статистику
@app.route('/api/game/finish', methods=['POST'])
def finish_game():
    try:
        user = get_current_user()
        if not user:
            return jsonify({'error': 'Не авторизован'}), 401

        data = request.get_json() or {}
        games_played = data.get('games_played', 1)

        # Обновляем статистику
        update_stats_data = {'type': 'games_played', 'value': games_played}
        request._cached_data = json.dumps(update_stats_data)
        return update_stats()

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Гарантируем существование всех необходимых файлов
    ensure_file_exists(DICTIONARY_PATH)
    ensure_file_exists(USER_WORDS_PATH)
    ensure_file_exists(USERS_PATH)
    
    # Для работы сессий нужен секретный ключ
    if not app.secret_key:
        app.secret_key = 'dev-secret-key-change-in-production'
    
    app.run(host='0.0.0.0', port=5001, debug=False)
      
