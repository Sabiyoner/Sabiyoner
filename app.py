from flask import Flask, render_template, request, redirect, url_for, session
import os
import psycopg2
from urllib.parse import urlparse
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'sabiyoner_gizli_kac_key_123'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        url = urlparse(DATABASE_URL)
        conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        return conn, 'postgres'
    else:
        import sqlite3
        conn = sqlite3.connect('sabiyoner.db')
        return conn, 'sqlite'

def init_db():
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    
    placeholder = '%s' if db_type == 'postgres' else '?'
    auto_inc = 'SERIAL PRIMARY KEY' if db_type == 'postgres' else 'INTEGER PRIMARY KEY AUTOINCREMENT'

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS users (
            id {auto_inc},
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            bio TEXT DEFAULT 'No bio yet',
            profile_pic TEXT DEFAULT 'https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png'
        )
    ''')
    
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS posts (
            id {auto_inc},
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT DEFAULT 'Ümumi',
            votes INTEGER DEFAULT 1,
            author TEXT DEFAULT 'Qonaq',
            created_at TEXT
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS likes (
            id {auto_inc},
            user_ip_or_name TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            UNIQUE(user_ip_or_name, post_id)
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS comments (
            id {auto_inc},
            post_id INTEGER NOT NULL,
            author TEXT NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY(post_id) REFERENCES posts(id) ON DELETE CASCADE
        )
    ''')

    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS follows (
            id {auto_inc},
            follower TEXT NOT NULL,
            following TEXT NOT NULL,
            UNIQUE(follower, following)
        )
    ''')
    
    cursor.execute('SELECT COUNT(*) FROM posts')
    count = cursor.fetchone()[0]
    if count == 0:
        now = datetime.now().strftime("%d.%m.%Y %H:%M")
        initial_posts = [
            ('İlk anonim etiraf!', 'Proqramlaşdırma öyrənəndə ilk 2 saat yalnız koda baxıb ağlayırdım...', 'İş Həyatı', 13, 'Qonaq', now),
            ('Müdirimə səhvən stiker göndərdim', 'İş qrupunda ciddi müzakirə gedirdi, yanlışlıqla gülməli pişik fotosu getdi.', 'Gülməli', 6, 'Qonaq', now)
        ]
        for p in initial_posts:
            cursor.execute(f'INSERT INTO posts (title, content, category, votes, author, created_at) VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder})', p)
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    sort_by = request.args.get('sort', 'top')
    category_filter = request.args.get('cat', 'Hamısı')
    search_query = request.args.get('q', '').strip()

    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    p = '%s' if db_type == 'postgres' else '?'
    
    query = 'SELECT id, title, content, category, votes, author, created_at FROM posts WHERE 1=1'
    params = []

    if category_filter != 'Hamısı':
        query += f' AND category = {p}'
        params.append(category_filter)

    if search_query:
        query += f' AND (LOWER(title) LIKE LOWER({p}) OR LOWER(content) LIKE LOWER({p}))'
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
        cursor.execute(f'SELECT author, content FROM comments WHERE post_id = {p} ORDER BY id ASC', (p_id,))
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

@app.route('/user/<username>')
def profile(username):
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    p = '%s' if db_type == 'postgres' else '?'

    # İstifadəçi məlumatı
    cursor.execute(f'SELECT username, bio, profile_pic FROM users WHERE username = {p}', (username,))
    user_info = cursor.fetchone()

    if not user_info:
        conn.close()
        return "İstifadəçi tapılmadı!", 404

    profile_user = {
        "username": user_info[0],
        "bio": user_info[1] or "No bio yet",
        "profile_pic": user_info[2] or "https://abs.twimg.com/sticky/default_profile_images/default_profile_400x400.png"
    }

    # Statistika
    cursor.execute(f'SELECT COUNT(*) FROM follows WHERE follower = {p}', (username,))
    following_count = cursor.fetchone()[0]

    cursor.execute(f'SELECT COUNT(*) FROM follows WHERE following = {p}', (username,))
    followers_count = cursor.fetchone()[0]

    cursor.execute(f'SELECT COALESCE(SUM(votes), 0) FROM posts WHERE author = {p}', (username,))
    total_likes = cursor.fetchone()[0]

    # İstifadəçinin postları
    cursor.execute(f'SELECT id, title, content, category, votes, created_at FROM posts WHERE author = {p} ORDER BY id DESC', (username,))
    user_posts_data = cursor.fetchall()
    
    user_posts = []
    for row in user_posts_data:
        user_posts.append({
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "category": row[3],
            "votes": row[4],
            "created_at": row[5]
        })

    current_user = session.get('username', 'Qonaq')
    is_following = False
    if current_user != 'Qonaq':
        cursor.execute(f'SELECT 1 FROM follows WHERE follower = {p} AND following = {p}', (current_user, username))
        is_following = cursor.fetchone() is not None

    conn.close()

    return render_template('profile.html', profile_user=profile_user, following_count=following_count, 
                           followers_count=followers_count, total_likes=total_likes, user_posts=user_posts,
                           current_user=current_user, is_following=is_following)

@app.route('/follow/<username>')
def follow_user(username):
    current_user = session.get('username', 'Qonaq')
    if current_user != 'Qonaq' and current_user != username:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        p = '%s' if db_type == 'postgres' else '?'
        try:
            cursor.execute(f'INSERT INTO follows (follower, following) VALUES ({p}, {p})', (current_user, username))
            conn.commit()
        except Exception:
            conn.rollback()
        conn.close()
    return redirect(url_for('profile', username=username))

@app.route('/unfollow/<username>')
def unfollow_user(username):
    current_user = session.get('username', 'Qonaq')
    if current_user != 'Qonaq':
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        p = '%s' if db_type == 'postgres' else '?'
        cursor.execute(f'DELETE FROM follows WHERE follower = {p} AND following = {p}', (current_user, username))
        conn.commit()
        conn.close()
    return redirect(url_for('profile', username=username))

@app.route('/update_profile', methods=['POST'])
def update_profile():
    current_user = session.get('username', 'Qonaq')
    if current_user != 'Qonaq':
        bio = request.form.get('bio')
        profile_pic = request.form.get('profile_pic')
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        p = '%s' if db_type == 'postgres' else '?'
        cursor.execute(f'UPDATE users SET bio = {p}, profile_pic = {p} WHERE username = {p}', (bio, profile_pic, current_user))
        conn.commit()
        conn.close()
    return redirect(url_for('profile', username=current_user))

@app.route('/create', methods=['POST'])
def create_post():
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category', 'Ümumi')
    author = session.get('username', 'Qonaq')
    created_at = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    if title and content:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        p = '%s' if db_type == 'postgres' else '?'
        cursor.execute(f'INSERT INTO posts (title, content, category, votes, author, created_at) VALUES ({p}, {p}, {p}, 1, {p}, {p})', 
                       (title, content, category, author, created_at))
        conn.commit()
        conn.close()
        
    return redirect(url_for('home'))

@app.route('/delete/<int:post_id>')
def delete_post(post_id):
    current_user = session.get('username', 'Qonaq')
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    p = '%s' if db_type == 'postgres' else '?'
    cursor.execute(f'DELETE FROM posts WHERE id = {p} AND author = {p}', (post_id, current_user))
    conn.commit()
    conn.close()
    return redirect(url_for('home'))

@app.route('/vote/<int:post_id>')
def vote(post_id):
    user_identifier = session.get('username', request.remote_addr)
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    p = '%s' if db_type == 'postgres' else '?'
    
    try:
        cursor.execute(f'INSERT INTO likes (user_ip_or_name, post_id) VALUES ({p}, {p})', (user_identifier, post_id))
        cursor.execute(f'UPDATE posts SET votes = votes + 1 WHERE id = {p}', (post_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        
    conn.close()
    return redirect(url_for('home'))

@app.route('/comment/<int:post_id>', methods=['POST'])
def add_comment(post_id):
    content = request.form.get('comment_text')
    author = session.get('username', 'Qonaq')
    if content:
        conn, db_type = get_db_connection()
        cursor = conn.cursor()
        p = '%s' if db_type == 'postgres' else '?'
        cursor.execute(f'INSERT INTO comments (post_id, author, content) VALUES ({p}, {p}, {p})', (post_id, author, content))
        conn.commit()
        conn.close()
    return redirect(url_for('home'))

@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    if username and password:
        try:
            conn, db_type = get_db_connection()
            cursor = conn.cursor()
            p = '%s' if db_type == 'postgres' else '?'
            cursor.execute(f'INSERT INTO users (username, password) VALUES ({p}, {p})', (username, password))
            conn.commit()
            conn.close()
            session['username'] = username
        except Exception:
            pass
    return redirect(url_for('home'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    conn, db_type = get_db_connection()
    cursor = conn.cursor()
    p = '%s' if db_type == 'postgres' else '?'
    cursor.execute(f'SELECT * FROM users WHERE username = {p} AND password = {p}', (username, password))
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
