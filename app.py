"""Common — an intentionally imperfect teaching application. See instructor/guide.md."""
import functools
import hmac
import os
import secrets
import sqlite3
import traceback
from pathlib import Path

import click
from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash

from db import close_db, get_db, seed
from lab import award, flag_response, hidden_post

ROOT = Path(__file__).parent


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'common-local-development-signing-key'),
        DATABASE=os.environ.get('DATABASE', str(ROOT / 'instance' / 'common.sqlite3')),
        MAX_CONTENT_LENGTH=64 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
    )
    if config:
        app.config.update(config)
    if not Path(app.config['DATABASE']).exists():
        seed(app.config['DATABASE'])
    app.teardown_appcontext(close_db)

    def login_required(view):
        @functools.wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                if request.path.startswith('/api/'):
                    abort(401)
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    @app.before_request
    def load_user():
        g.user = get_db().execute('SELECT * FROM users WHERE id=?', (session.get('user_id'),)).fetchone()
        session.setdefault('csrf', secrets.token_hex(24))
        if request.method in {'POST', 'PATCH', 'DELETE', 'PUT'}:
            token = request.headers.get('X-CSRF-Token') or request.form.get('csrf', '')
            if not hmac.compare_digest(token.encode('utf-8'), session['csrf'].encode('utf-8')):
                abort(400, 'Your session changed. Refresh the page and try again.')

    @app.context_processor
    def template_context():
        return {'me': g.user, 'csrf': session['csrf'], 'lab_flags': g.get('lab_flags', [])}

    @app.after_request
    def response_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-Powered-By'] = 'Common/0.8.4 (Flask; SQLite)'
        response.headers['Cache-Control'] = 'no-store'
        return flag_response(response)

    def json_object():
        data = request.get_json()
        if not isinstance(data, dict):
            abort(400, 'Send a JSON object.')
        return data

    def text_value(data, key, limit):
        value = data.get(key, '')
        if not isinstance(value, str) or len(value.strip()) > limit:
            abort(400, f'{key.capitalize()} must be text of at most {limit} characters.')
        return value.strip()

    def public_user(user):
        return {key: user[key] for key in ('id', 'username', 'name', 'bio', 'location', 'color', 'role')}

    def post_query(where='1=1', params=()):
        return get_db().execute(f'''SELECT p.*, u.name, u.username, u.color,
            (SELECT count(*) FROM likes WHERE post_id=p.id) AS like_count,
            (SELECT count(*) FROM comments WHERE post_id=p.id) AS comment_count,
            EXISTS(SELECT 1 FROM likes WHERE post_id=p.id AND user_id=?) AS liked,
            EXISTS(SELECT 1 FROM saves WHERE post_id=p.id AND user_id=?) AS saved
            FROM posts p JOIN users u ON u.id=p.user_id WHERE {where} ORDER BY p.id DESC''',
            (g.user['id'], g.user['id'], *params)).fetchall()

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.user is not None:
            return redirect(url_for('feed'))
        error = None
        if request.method == 'POST':
            user = get_db().execute('SELECT * FROM users WHERE username=?', (request.form.get('username', '').lower().strip(),)).fetchone()
            if user and check_password_hash(user['password'], request.form.get('password', '')):
                session.clear()
                session['user_id'] = user['id']
                return redirect(url_for('feed'))
            error = 'That username and password don’t match. Try again.'
        return render_template('auth.html', error=error, signup=False)

    @app.route('/signup', methods=['GET', 'POST'])
    def signup():
        if g.user is not None:
            return redirect(url_for('feed'))
        error = None
        if request.method == 'POST':
            data = request.form
            username = data.get('username', '').lower().strip()
            name = data.get('name', '').strip()
            email = data.get('email', '').strip()
            if not username.isalnum() or not 3 <= len(username) <= 24 or len(data.get('password', '')) < 8 or not 1 <= len(name) <= 80 or not 1 <= len(email) <= 180 or '@' not in email:
                error = 'Use a 3–24 character username, your name, an email, and a password of at least 8 characters.'
            elif get_db().execute('SELECT id FROM users WHERE username=? OR email=?', (username, email)).fetchone():
                error = 'That username or email is already in use.'
            else:
                cursor = get_db().execute('INSERT INTO users (username,name,email,password) VALUES (?,?,?,?)', (username, name, email, generate_password_hash(data['password'])))
                get_db().commit()
                session.clear()
                session['user_id'] = cursor.lastrowid
                return redirect(url_for('feed'))
        return render_template('auth.html', error=error, signup=True)

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    @app.get('/')
    @login_required
    def feed():
        tab = request.args.get('tab', 'feed')
        if tab == 'saved':
            posts = post_query("(p.visibility='public' OR p.user_id=?) AND EXISTS(SELECT 1 FROM saves WHERE post_id=p.id AND user_id=?)", (g.user['id'], g.user['id']))
        else:
            posts = post_query("p.visibility='public'")
        return render_template('feed.html', posts=posts, tab=tab, people=get_db().execute('SELECT * FROM users WHERE id != ? LIMIT 3', (g.user['id'],)).fetchall())

    @app.get('/people/<username>')
    @login_required
    def profile(username):
        user = get_db().execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if user is None:
            abort(404)
        posts = post_query("p.user_id=? AND (p.visibility='public' OR p.user_id=?)", (user['id'], g.user['id']))
        return render_template('profile.html', profile=user, posts=posts, tab='profile')

    @app.get('/posts/<int:post_id>')
    @login_required
    def post_page(post_id):
        # LAB BAC-01: direct lookup lacks the visibility predicate used by the feed.
        posts = post_query('p.id=?', (post_id,))
        if not posts:
            abort(404)
        if hidden_post(posts[0]):
            award('BAC-01')
        return render_template('post.html', posts=posts, tab='feed')

    @app.get('/settings')
    @login_required
    def settings():
        return render_template('settings.html', tab='settings')

    @app.get('/messages')
    @login_required
    def inbox():
        threads = get_db().execute('''SELECT c.*, (SELECT body FROM messages WHERE conversation_id=c.id ORDER BY id DESC LIMIT 1) AS preview
            FROM conversations c JOIN participants p ON c.id=p.conversation_id WHERE p.user_id=?''', (g.user['id'],)).fetchall()
        return render_template('messages.html', threads=threads, tab='messages')

    @app.get('/api/users/<int:user_id>')
    @login_required
    def user_detail(user_id):
        user = get_db().execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if user is None:
            abort(404)
        # LAB INFO-01: private fields added to an otherwise public profile serializer.
        if user_id != g.user['id'] and g.user['role'] != 'admin':
            award('INFO-01')
        return jsonify(**public_user(user), email=user['email'])

    @app.patch('/api/users/<int:user_id>')
    @login_required
    def update_user(user_id):
        data = json_object()
        target = get_db().execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if target is None:
            abort(404)
        # LAB BAC-02 / BAC-03: neither object ownership nor field-level authorization.
        allowed = {'name': 80, 'bio': 500, 'location': 100, 'email': 180, 'role': 500}
        updates = {key: text_value(data, key, limit) for key, limit in allowed.items() if key in data}
        if 'name' in updates and not updates['name']:
            abort(400, 'Your name cannot be blank.')
        if 'email' in updates and '@' not in updates['email']:
            abort(400, 'Enter an email address.')
        if updates:
            columns = ', '.join(f'{key}=?' for key in updates)
            try:
                get_db().execute(f'UPDATE users SET {columns} WHERE id=?', (*updates.values(), user_id))
                get_db().commit()
            except sqlite3.IntegrityError:
                get_db().rollback()
                abort(409, 'That email is already in use.')
            changed = {key for key in updates if updates[key] != target[key]}
            if changed and g.user['role'] != 'admin':
                if user_id != g.user['id']:
                    award('BAC-02')
                if 'role' in changed and updates['role'] == 'admin':
                    award('BAC-03')
        return jsonify(ok=True)

    @app.get('/api/posts/<int:post_id>')
    @login_required
    def post_detail(post_id):
        posts = post_query('p.id=?', (post_id,))
        if not posts:
            abort(404)
        if hidden_post(posts[0]):
            award('BAC-01')
        return jsonify(dict(posts[0]))

    @app.post('/api/posts')
    @login_required
    def create_post():
        data = json_object()
        body = text_value(data, 'body', 2000)
        visibility = data.get('visibility', 'public')
        if not body or not isinstance(visibility, str) or visibility not in {'public', 'circle', 'private'}:
            abort(400, 'Write a post of 1–2000 characters and choose an audience.')
        cursor = get_db().execute('INSERT INTO posts (user_id,body,visibility) VALUES (?,?,?)', (g.user['id'], body, visibility))
        get_db().commit()
        return jsonify(id=cursor.lastrowid), 201

    @app.delete('/api/posts/<int:post_id>')
    @login_required
    def delete_post(post_id):
        # LAB BAC-04: authenticated users can delete another member’s post.
        post = get_db().execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
        if post is None:
            abort(404)
        db = get_db()
        with db:
            for table in ('likes', 'saves', 'comments', 'reports'):
                db.execute(f'DELETE FROM {table} WHERE post_id=?', (post_id,))
            db.execute('DELETE FROM posts WHERE id=?', (post_id,))
        if post['user_id'] != g.user['id'] and g.user['role'] != 'admin':
            award('BAC-04')
        return jsonify(ok=True)

    @app.post('/api/posts/<int:post_id>/<action>')
    @login_required
    def post_action(post_id, action):
        post = get_db().execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
        if post is None:
            abort(404)
        if action not in {'like', 'save'}:
            abort(404)
        table = {'like': 'likes', 'save': 'saves'}[action]
        db = get_db()
        exists = db.execute(f'SELECT 1 FROM {table} WHERE user_id=? AND post_id=?', (g.user['id'], post_id)).fetchone()
        if exists:
            db.execute(f'DELETE FROM {table} WHERE user_id=? AND post_id=?', (g.user['id'], post_id))
        else:
            db.execute(f'INSERT INTO {table} VALUES (?,?)', (g.user['id'], post_id))
        db.commit()
        if hidden_post(post):
            award('BAC-01')
        return jsonify(active=not bool(exists), count=db.execute(f'SELECT count(*) FROM {table} WHERE post_id=?', (post_id,)).fetchone()[0])

    @app.route('/api/posts/<int:post_id>/comments', methods=['GET', 'POST'])
    @login_required
    def comments(post_id):
        post = get_db().execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
        if post is None:
            abort(404)
        if request.method == 'POST':
            body = text_value(json_object(), 'body', 1000)
            if not body:
                abort(400, 'Write a comment of 1–1000 characters.')
            get_db().execute('INSERT INTO comments (user_id,post_id,body) VALUES (?,?,?)', (g.user['id'], post_id, body))
            get_db().commit()
        rows = get_db().execute('SELECT c.body, u.name FROM comments c JOIN users u ON u.id=c.user_id WHERE post_id=? ORDER BY c.id', (post_id,)).fetchall()
        if hidden_post(post) and (rows or request.method == 'POST'):
            award('BAC-01')
        return jsonify([dict(row) for row in rows])

    @app.route('/api/conversations/<int:conversation_id>', methods=['GET', 'POST'])
    @login_required
    def conversation(conversation_id):
        # LAB BAC-05: direct reads omit the membership check used for writes.
        thread = get_db().execute('SELECT * FROM conversations WHERE id=?', (conversation_id,)).fetchone()
        if thread is None:
            abort(404)
        participant = get_db().execute('SELECT 1 FROM participants WHERE conversation_id=? AND user_id=?', (conversation_id, g.user['id'])).fetchone()
        if request.method == 'POST':
            if not participant:
                abort(403)
            body = text_value(json_object(), 'body', 2000)
            if not body:
                abort(400, 'Write a message of 1–2000 characters.')
            get_db().execute('INSERT INTO messages (conversation_id,sender_id,body) VALUES (?,?,?)', (conversation_id, g.user['id'], body))
            get_db().commit()
        messages = get_db().execute('SELECT m.*, u.name FROM messages m JOIN users u ON u.id=m.sender_id WHERE conversation_id=? ORDER BY m.id', (conversation_id,)).fetchall()
        if not participant:
            award('BAC-05')
        return jsonify(subject=thread['subject'], messages=[dict(m) for m in messages])

    @app.get('/staff')
    @login_required
    def staff():
        if g.user['role'] != 'admin':
            abort(403)
        return render_template('staff.html', tab='staff', reports=get_db().execute('SELECT * FROM reports').fetchall())

    @app.get('/api/staff/reports')
    @login_required
    def staff_reports():
        # LAB BAC-06: UI checks role; the underlying API only checks login.
        if g.user['role'] != 'admin':
            award('BAC-06')
        return jsonify([dict(r) for r in get_db().execute('SELECT * FROM reports')])

    @app.post('/api/staff/reports/<int:report_id>/resolve')
    @login_required
    def resolve_report(report_id):
        report = get_db().execute('SELECT * FROM reports WHERE id=?', (report_id,)).fetchone()
        if report is None:
            abort(404)
        get_db().execute("UPDATE reports SET status='resolved' WHERE id=?", (report_id,))
        get_db().commit()
        if g.user['role'] != 'admin' and report['status'] != 'resolved':
            award('BAC-06')
        return jsonify(ok=True)

    @app.get('/robots.txt')
    def robots():
        return 'User-agent: *\nDisallow: /staff\nDisallow: /ops/\nDisallow: /api/internal/\n', 200, {'Content-Type': 'text/plain'}

    @app.get('/ops/')
    def ops():
        return render_template('ops.html')

    @app.get('/ops/common.env.bak')
    def backup():
        # LAB INFO-02: operational artifact with the actual lab signing key, no real services.
        flag = award('INFO-02')
        return f"APP_NAME=common\nAPP_VERSION=0.8.4\nSECRET_KEY={app.config['SECRET_KEY']}\nDATABASE_PATH={app.config['DATABASE']}\nINTERNAL_STATUS=/api/internal/health\nFLAG={flag}\n", 200, {'Content-Type': 'text/plain'}

    @app.get('/api/internal/health')
    def health():
        # Reconnaissance metadata alone is not a graded exploit.
        return jsonify(service='common-web', version='0.8.4', database=app.config['DATABASE'], environment='staging', backup='/ops/common.env.bak', release='willow-2026.04')

    @app.get('/api/search')
    @login_required
    def search():
        # LAB INFO-03: invalid limit produces an unhandled exception and diagnostic response.
        limit = min(max(int(request.args.get('limit', '10')), 1), 50)
        query = request.args.get('q', '')
        rows = get_db().execute("SELECT id,username,name,bio,color FROM users WHERE name LIKE ? OR username LIKE ? LIMIT ?", (f'%{query}%', f'%{query}%', limit))
        return jsonify([dict(row) for row in rows])

    @app.errorhandler(Exception)
    def errors(error):
        if isinstance(error, HTTPException):
            if request.path.startswith('/api/'):
                return jsonify(error=error.description), error.code
            return render_template('error.html', code=error.code, message=error.description), error.code
        # Deliberate diagnostic disclosure, NOT Werkzeug's executable debugger.
        if request.endpoint == 'search' and isinstance(error, ValueError):
            award('INFO-03')
        return render_template('diagnostic.html', detail=traceback.format_exc(), database=app.config['DATABASE']), 500

    @app.cli.command('reset-db')
    @click.option('--yes', is_flag=True, help='Skip confirmation; destroys all lab data.')
    def reset_db(yes):
        """Replace the lab database with its original fixtures."""
        if not yes:
            click.confirm('Delete all Common data and restore fixtures?', abort=True)
        close_db()
        Path(app.config['DATABASE']).unlink(missing_ok=True)
        seed(app.config['DATABASE'])
        click.echo('Common fixtures restored.')

    return app


if __name__ == '__main__':
    # Refresh templates during local UI work without enabling the executable debugger.
    create_app({'TEMPLATES_AUTO_RELOAD': True}).run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '5000')), debug=False)
