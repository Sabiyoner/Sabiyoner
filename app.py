from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sabiyoner_gizli_kac_key_123'

def init_db():
    conn = sqlite3.connect('sabiyoner.db')
    cursor = conn.cursor()
    
    # İstifadəçilər
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Postlar
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'Ümumi',
            votes INTEGER DEFAULT 1,
            author TEXT DEFAULT 'Qonaq',
            created_at TEXT
        )
    ''')

    # Like tarixçəsi (Təkrar like-ın qarşısını almaq üçün)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_ip_or_name TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            UNIQUE(user_ip_or_name, post_id)
        )
    ''')

    # Rəylər
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(post_id) REFERENCES posts(id)
        )
    ''')
    
    # İlkin postlar
    cursor.execute('SELECT COUNT(*) FROM posts')
    if cursor.fetchone()[0] == 0:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        initial_posts = [
            ('İlk anonim etiraf!', 'Proqramlaşdırma öyrənəndə ilk 2 saat yalnız koda baxıb ağlayırdım...', 'İş Həyatı', 13, 'Qonaq', now),
            ('Müdirimə səhvən stiker göndərdim', 'İş qrupunda ciddi müzakirə gedirdi, yanlışlıqla gülməli pişik fotosu getdi.', 'Gülməli', 6, 'Qonaq', now)
        ]
        cursor.executemany('INSERT INTO posts (title, content, category, votes, author, created_at) VALUES (?, ?, ?, ?, ?, ?)', initial_posts)
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    sort_by = request.args.get('sort', 'top')
    category_filter = request.args.get('cat', 'Hamısı')
    search_query = request.args.get('q', '').strip()

    conn = sqlite3.connect('sabiyoner.db')
    cursor = conn.cursor()
    
    query = 'SELECT id, title, content, category, votes, author, created_at FROM posts WHERE 1=1'
    params = []

    if category_filter != 'Hamısı':
        query += ' AND category = ?'
        params.append(category_filter)

    if search_query:
        query += ' AND (LOWER(title) LIKE LOWER(?) OR LOWER(content) LIKE LOWER(?))'
        params.extend([f'%{search_query}%', f'%{search_query}%'])

    if sort_by == 'new':
        query += ' ORDER BY id DESC'
    else:
        query += ' ORDER BY votes DESC'

    cursor.execute(query, params)
    posts_data = cursor.fetchall()

    posts = []
    for row in posts_data:
        p_id = row[0]
        cursor.execute('SELECT author, content FROM comments WHERE post_id = ? ORDER BY id ASC', (p_id,))
        comments_data = cursor.fetchall()
        comments = [{"author": c[0], "content": c[1]} for c in comments_data]

        posts.append({
            "id": p_id,
            "title": row[1],
            "content": row[2],
            "category": row[3],
            "votes": row[4],
            "author": row[5],
            "created_at": row[6] if len(row) > 6 and row[6] else 'Bəlli deyil',
            "comments": comments
        })

    conn.close()
    current_user = session.get('username', 'Qonaq')

    return render_template('index.html', posts=posts, current_user=current_user, 
                           current_sort=sort_by, current_cat=category_filter, search_q=search_query)

@app.route('/create', methods=['POST'])
def create_post():
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category', 'Ümumi')
    author = session.get('username', 'Qonaq')
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    if title and content:
        conn = sqlite3.connect('sabiyoner.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO posts (title, content, category, votes, author, created_at) VALUES (?, ?, ?, ?, ?, ?)', 
                       (title, content, category, 1, author, created_at))
        conn.commit()
        conn.close()
        
    return redirect(url_for('home'))

@app.route('/delete/<int:post_id>')
def delete_post(post_id):
    current_user = session.get('username', 'Qonaq')
    conn = sqlite3.connect('sabiyoner.db')
    cursor = conn.cursor()
    # Yalnız postun öz müəllifi silə bilsin
    cursor.execute('DELETE FROM posts WHERE id = ? AND author = ?', (post_id, current_user))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/vote/<int:post_id>')
def vote(post_id):
    user_identifier = session.get('username', request.remote_addr) # Giriş edibsə adı, etməyibsə IP ünvanı
    conn = sqlite3.connect('sabiyoner.db')
    cursor = conn.cursor()
    
    try:
        # Təkrar like yoxlanışı
        cursor.execute('INSERT INTO likes (user_ip_or_name, post_id) VALUES (?, ?)', (user_identifier, post_id))
        cursor.execute('UPDATE posts SET votes = votes + 1 WHERE id = ?', (post_id,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Artıq like basıb, heç nə etmirik
        
    conn.close()
    return redirect(url_for('home'))

@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    content = request.form.get('comment_text')
    author = session.get('username', 'Qonaq')
    if content:
        conn = sqlite3.connect('sabiyoner.db')
        cursor = conn.cursor()
        cursor.execute('INSERT INTO comments (post_id, author, content) VALUES (?, ?, ?)', (post_id, author, content))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    if username and password:
        try:
            conn = sqlite3.connect('sabiyoner.db')
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            conn.close()
            session['username'] = username
        except sqlite3.IntegrityError:
            pass
    return redirect(url_for('home'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    conn = sqlite3.connect('sabiyoner.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ? AND password = ?', (username, password))
    user = cursor.fetchone()
    conn.close()
    if user:
        session['username'] = username
    return redirect(url_for('home'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)