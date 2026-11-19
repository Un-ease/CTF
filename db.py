"""SQLite storage and repeatable, entirely fictional fixtures."""
import sqlite3
from pathlib import Path
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 email TEXT UNIQUE NOT NULL, password TEXT NOT NULL, bio TEXT NOT NULL DEFAULT '',
 role TEXT NOT NULL DEFAULT 'member', location TEXT NOT NULL DEFAULT 'Northside',
 color TEXT NOT NULL DEFAULT 'lilac');
CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, body TEXT NOT NULL,
 visibility TEXT NOT NULL DEFAULT 'public', art TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE likes (user_id INTEGER, post_id INTEGER, PRIMARY KEY(user_id, post_id));
CREATE TABLE saves (user_id INTEGER, post_id INTEGER, PRIMARY KEY(user_id, post_id));
CREATE TABLE comments (id INTEGER PRIMARY KEY, user_id INTEGER, post_id INTEGER,
 body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE conversations (id INTEGER PRIMARY KEY, subject TEXT NOT NULL);
CREATE TABLE participants (conversation_id INTEGER, user_id INTEGER,
 PRIMARY KEY(conversation_id, user_id));
CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id INTEGER, sender_id INTEGER,
 body TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE reports (id INTEGER PRIMARY KEY, post_id INTEGER, reason TEXT, status TEXT DEFAULT 'open');
"""


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_error=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def seed(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    users = [
        ('alex', 'Alex Morgan', 'alex@common.test', 'alex-common-2026', 'Making things, taking the long way home. Usually at the ceramics studio.', 'member', 'Northside', 'lilac'),
        ('maya', 'Maya Chen', 'maya@common.test', 'maya-studio-2026', 'Designer, plant collector, occasional printmaker. Building a little studio on Willow Street.', 'member', 'Willow Street', 'peach'),
        ('jules', 'Jules Rivera', 'jules@common.test', 'jules-film-2026', 'Photographs of ordinary days. Say hello if you see me at Paper & Cup.', 'member', 'Old Town', 'blue'),
        ('nia', 'Nia Brooks', 'nia@common.test', 'nia-garden-2026', 'Growing a community, one very wonky tomato at a time.', 'member', 'Northside', 'green'),
        ('ellis', 'Ellis Park', 'ellis@common.test', 'ellis-common-2026', 'Keeping the lights on at Common. Here for good neighbors and good coffee.', 'admin', 'Northside', 'yellow'),
    ]
    for username, name, email, password, bio, role, location, color in users:
        db.execute('INSERT INTO users (username,name,email,password,bio,role,location,color) VALUES (?,?,?,?,?,?,?,?)',
                   (username, name, email, generate_password_hash(password), bio, role, location, color))
    posts = [
        (2, 'A little corner of the studio, finally coming together. The afternoon light is doing most of the work. ☀️', 'public', 'studio'),
        (3, 'Saturday, no plans. Just a camera and the other side of town.\n\nA few frames from this morning’s walk.', 'public', 'walk'),
        (4, 'The seed swap is back! Bring what you have, take what you need. Sunday at 10, behind the library. Beginners especially welcome. 🌱', 'public', None),
        (1, 'Does anyone know a good spot to get a small run of risograph prints made? Working on something for the weekend market.', 'public', None),
        (5, 'Small update: you can now save posts to come back to later. Look for the bookmark in the corner. Thanks for making this place feel like a neighborhood.', 'public', None),
        (2, 'Studio notes, just for the close circle: the door code for the launch is 4826. Please don’t share publicly. The client preview is on Thursday.', 'circle', None),
        (5, 'Draft for Monday: the community fund has a fictional reserve of $12,400. Internal reference COMMON-FUND-072. Waiting on approval before announcing.', 'private', None),
    ]
    db.executemany('INSERT INTO posts (user_id,body,visibility,art) VALUES (?,?,?,?)', posts)
    db.executemany('INSERT INTO likes VALUES (?,?)', [(1,1),(3,1),(4,1),(5,1),(2,2),(4,2),(3,3),(1,3)])
    db.executemany('INSERT INTO comments (user_id,post_id,body) VALUES (?,?,?)', [
        (4,1,'That light! Can’t wait to see the space in person.'),
        (3,1,'The chair is such a good find.'),
        (2,4,'Try Ink House on Mill Street. Ask for Sam!'),
        (5,7,'Reviewer note: keep the COMMON-FUND-072 figures private until the board approves the draft.'),
    ])
    db.executemany('INSERT INTO conversations VALUES (?,?)', [(1,'Weekend market'),(2,'Studio launch'),(3,'Community fund')])
    db.executemany('INSERT INTO participants VALUES (?,?)', [(1,1),(1,2),(2,2),(2,3),(3,4),(3,5)])
    db.executemany('INSERT INTO messages (conversation_id,sender_id,body) VALUES (?,?,?)', [
        (1,2,'Hey Alex! Are you bringing your prints to the market this weekend?'),
        (1,1,'That’s the plan! Just figuring out the final colors.'),
        (1,2,'Save me one of the blue ones. I’ll bring coffee.'),
        (2,2,'Keeping this between us until the announcement: the preview is Thursday. Guest list reference: STUDIO-GUEST-83.'),
        (2,3,'Got it. I’ll bring the camera and keep the photos private until Friday.'),
        (3,5,'The fund report is ready. Internal approval phrase: orchard-paper-lantern. All figures are fictional.'),
    ])
    db.execute('INSERT INTO reports (post_id,reason) VALUES (?,?)', (4,'Duplicate market announcement — please review.'))
    db.commit()
    db.close()
