from flask import Flask, render_template, request, session, redirect, url_for, flash, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3
import os

# Создание экземпляра Flask-приложения
app = Flask(__name__)
# __name__ - это имя текущего модуля

# Установка секретного ключа для сессий
app.secret_key = os.urandom(24)
# Генерирует случайный ключ

# Настройка папки для загрузки файлов (аватарок, спрайтов)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
# Настройка разрешенных расширений файлов для загрузки
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
# Установка максимального размера загружаемого файла (в байтах)
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024


# Функция для проверки, является ли расширение файла разрешенным
def allowed_file(filename):
    # Проверяет, есть ли точка в имени файла и является ли расширение (после точки) допустимым
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# Функция для получения соединения с базой данных
def get_db():
    # Проверяет, существует ли соединение с базой данных в контексте запроса (g)
    if 'db' not in g:
        # Если соединения нет, то устанавливает соединение с базой данных 'spriteshope.db'
        g.db = sqlite3.connect('spriteshope.db')
        # Устанавливает row_factory в sqlite3.Row, чтобы возвращать результаты запросов в виде словарей
        g.db.row_factory = sqlite3.Row
    return g.db


# Функция для инициализации базы данных (создание таблиц, если их нет)
def init_db():
    # Использует app.app_context(), чтобы получить доступ к контексту приложения
    with app.app_context():
        db = get_db()
        # Выполняет SQL-запросы для создания таблиц users и sprites
        db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                balance INTEGER DEFAULT 100,
                avatar TEXT DEFAULT 'default-avatar.png',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )''')
        db.execute('''
            CREATE TABLE IF NOT EXISTS sprites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price INTEGER NOT NULL,
                short_description TEXT NOT NULL,
                long_description TEXT NOT NULL,
                image_path TEXT DEFAULT 'default-sprite.png',
                seller_id INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (seller_id) REFERENCES users(id)
            )''')
        # Фиксирует изменения в базе данных
        db.commit()


# Вызывает функцию инициализации базы данных при запуске приложения
init_db()


# Функция для закрытия соединения с базой данных после обработки запроса
@app.teardown_appcontext
def close_db(error):
    # Проверяет, существует ли соединение с базой данных в контексте запроса
    if hasattr(g, 'db'):
        # Закрывает соединение с базой данных
        g.db.close()


# Определение маршрута для главной страницы ('/')
@app.route('/')
def home():
    # Получает соединение с базой данных
    db = get_db()
    # Получает значение параметра 'search' из строки запроса (если он есть)
    search = request.args.get('search', '')
    # Выполняет SQL-запрос для получения спрайтов, соответствующих поисковому запросу
    sprites = db.execute('''
        SELECT sprites.*, users.username 
        FROM sprites 
        JOIN users ON sprites.seller_id = users.id
        WHERE name LIKE ? 
        ORDER BY created_at DESC
    ''', ('%' + search + '%',)).fetchall()
    # Отображает шаблон 'index.html', передавая ему список спрайтов
    return render_template('index.html', sprites=sprites)


# Определение маршрута для страницы регистрации ('/register')
@app.route('/register', methods=['GET', 'POST'])
def register():
    # Обрабатывает POST-запрос (отправка данных формы)
    if request.method == 'POST':
        # Получает данные из формы регистрации
        username = request.form['username']
        password = request.form['password']
        # Получает соединение с базой данных
        db = get_db()

        # Проверяет длину пароля
        if len(password) < 6:
            # Если пароль слишком короткий, отображает сообщение об ошибке
            flash('Пароль должен быть не менее 6 символов', 'error')
            # Перенаправляет пользователя на страницу регистрации
            return redirect(url_for('register'))

        try:
            # Пытается добавить нового пользователя в базу данных
            db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, generate_password_hash(password))  # Хэширует пароль перед сохранением
            )
            # Фиксирует изменения в базе данных
            db.commit()
            # Отображает сообщение об успешной регистрации
            flash('Регистрация успешна! Войдите в систему', 'success')
            # Перенаправляет пользователя на страницу входа
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            # Если имя пользователя уже занято, отображает сообщение об ошибке
            flash('Это имя пользователя уже занято', 'error')
    # Обрабатывает GET-запрос (отображение формы регистрации)
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    # Обрабатывает GET и POST запросы для страницы входа.

    # Если получен POST запрос (форма отправлена):
    if request.method == 'POST':
        # Получает имя пользователя и пароль из формы.
        username = request.form['username']
        password = request.form['password']
        # Получает соединение с базой данных.
        db = get_db()

        # Ищет пользователя в базе данных по имени пользователя.
        user = db.execute(
            'SELECT * FROM users WHERE username = ?',
            (username,)
        ).fetchone()

        # Проверяет, найден ли пользователь и совпадает ли введенный пароль с хешем пароля в базе данных.
        if user and check_password_hash(user['password'], password):
            # Если учетные данные верны:
            # Сохраняет ID пользователя в сессии.  Это "логинит" пользователя.
            session['user_id'] = user['id']
            # Перенаправляет пользователя на главную страницу.
            return redirect(url_for('home'))

        # Если учетные данные неверны:
        flash('Неверные учетные данные', 'error')  # Отображает сообщение об ошибке.

    # Если получен GET запрос (запрос страницы входа):
    return render_template('login.html')  # Отображает форму входа.


@app.route('/logout')
def logout():
    # Обрабатывает запрос на выход из системы.
    # Удаляет ID пользователя из сессии.  Это "разлогинивает" пользователя.
    session.pop('user_id', None)
    # Перенаправляет пользователя на главную страницу.
    return redirect(url_for('home'))


@app.route('/about')
def about():
    # Обрабатывает запрос на страницу "О сайте".
    # Отображает шаблон 'about.html'.
    return render_template('about.html')


@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    # Обрабатывает GET и POST запросы для страницы добавления товара.

    # Проверяет, авторизован ли пользователь.
    if 'user_id' not in session:
        # Если пользователь не авторизован, перенаправляет на страницу входа.
        return redirect(url_for('login'))

    # Если получен POST запрос (форма отправлена):
    if request.method == 'POST':
        try:
            # Получает данные из формы добавления товара.
            name = request.form['name']
            price = int(request.form['price'])
            short_desc = request.form['short_description']
            long_desc = request.form['long_description']
            file = request.files['image']  # Получает файл изображения.
            filename = 'default-sprite.png'  # Имя файла по умолчанию.

            # Обрабатывает загрузку изображения, если оно было отправлено.
            if file and allowed_file(file.filename):
                # Если файл был отправлен и имеет разрешенное расширение:
                filename = secure_filename(file.filename)  # Безопасное имя файла.
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))  # Сохраняет файл.

            # Получает соединение с базой данных.
            db = get_db()
            # Добавляет информацию о товаре в базу данных.
            db.execute('''
                INSERT INTO sprites 
                (name, price, short_description, long_description, image_path, seller_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, price, short_desc, long_desc, filename, session['user_id']))
            # Фиксирует изменения в базе данных.
            db.commit()
            # Отображает сообщение об успешном добавлении товара.
            flash('Товар успешно добавлен!', 'success')
            # Перенаправляет пользователя на страницу профиля.
            return redirect(url_for('profile'))  # Assuming there's a profile route

        except Exception as e:
            # Обрабатывает возможные исключения и отображает сообщение об ошибке.
            flash(f'Ошибка: {str(e)}', 'error')

    # Если получен GET запрос (запрос страницы добавления товара):
    return render_template('add_item.html')  # Отображает форму добавления товара.


@app.route('/sprite/<int:sprite_id>')
def sprite_detail(sprite_id):
    # Обрабатывает запрос на страницу с детальной информацией о товаре.
    # sprite_id: ID товара, информацию о котором нужно отобразить.

    # Получает соединение с базой данных.
    db = get_db()
    # Извлекает информацию о товаре и продавце из базы данных.
    sprite = db.execute('''
        SELECT s.*, u.username, u.avatar 
        FROM sprites s
        JOIN users u ON s.seller_id = u.id
        WHERE s.id = ?
    ''', (sprite_id,)).fetchone()
    # Отображает шаблон 'sprite_detail.html', передавая ему информацию о товаре.
    return render_template('sprite_detail.html', sprite=sprite)


@app.route('/delete/<int:sprite_id>', methods=['POST'])
def delete(sprite_id):
    # Обрабатывает POST-запрос на удаление товара (спрайта).
    # sprite_id: ID товара, который нужно удалить.

    # Проверяет, авторизован ли пользователь.
    if 'user_id' not in session:
        # Если пользователь не авторизован, перенаправляет на страницу входа.
        return redirect(url_for('login'))

    # Получает соединение с базой данных.
    db = get_db()
    try:
        # Пытается удалить товар из базы данных, проверяя, что пользователь является владельцем товара.
        db.execute(
            'DELETE FROM sprites WHERE id = ? AND seller_id = ?',
            (sprite_id, session['user_id']))  # Удаляет товар только если ID товара и ID продавца совпадают

        # Фиксирует изменения в базе данных.
        db.commit()

        # Отображает сообщение об успешном удалении.
        flash('Товар удален', 'success')
    except Exception as e:
        # Если произошла ошибка, отменяет изменения в базе данных.
        db.rollback()
        # Отображает сообщение об ошибке.
        flash('Ошибка удаления', 'error')

    # Перенаправляет пользователя на страницу профиля.
    return redirect(url_for('profile'))


@app.route('/profile')
def profile():
    # Обрабатывает запрос на страницу профиля пользователя.

    # Проверяет, авторизован ли пользователь.
    if 'user_id' not in session:
        # Если пользователь не авторизован, перенаправляет на страницу входа.
        return redirect(url_for('login'))

    # Получает соединение с базой данных.
    db = get_db()

    # Получает информацию о пользователе из базы данных.
    user = db.execute(
        'SELECT * FROM users WHERE id = ?',
        (session['user_id'],)  # Использует ID пользователя из сессии для получения информации
    ).fetchone()

    # Получает список товаров, принадлежащих пользователю, из базы данных.
    sprites = db.execute(
        'SELECT * FROM sprites WHERE seller_id = ?',
        (session['user_id'],)  # Использует ID пользователя из сессии для получения списка товаров
    ).fetchall()

    # Отображает шаблон 'profile.html', передавая ему информацию о пользователе и список его товаров.
    return render_template('profile.html', user=user, sprites=sprites)


if __name__ == '__main__':
    # Выполняется только при запуске этого файла напрямую (не как модуль).

    # Создает папку для загрузок, если ее не существует.
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    # Запускает Flask-приложение в режиме отладки.  В режиме отладки сервер автоматически перезагружается при изменении кода.
    app.run(debug=True)
