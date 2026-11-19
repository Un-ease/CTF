"""Accidental correctness bugs, kept separate from intentional teaching flaws."""
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import create_app
from lab import FLAGS


class CorrectnessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.database = str(Path(self.temp.name) / 'correctness.sqlite3')
        self.app = create_app({'TESTING': True, 'DATABASE': self.database, 'SECRET_KEY': 'correctness-key'})
        self.client = self.app.test_client()
        self.client.get('/login')
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        self.client.post('/login', data={'csrf': csrf, 'username': 'alex', 'password': 'alex-common-2026'})
        self.client.get('/')

    def mutate(self, path, data):
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        return self.client.patch(path, json=data, headers={'X-CSRF-Token': csrf})

    def test_profile_update_identifies_the_actual_target(self):
        response = self.mutate('/api/users/2', {'name': 'Alex Morgan'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['user']['id'], 2)
        self.assertEqual(response.json['user']['username'], 'maya')
        self.assertEqual(response.json['user']['name'], 'Alex Morgan')
        self.assertEqual(response.json['changed_fields'], ['name'])
        self.assertNotIn('email', response.json['user'])
        self.assertNotIn('password', response.json['user'])
        self.assertEqual(response.json['flags'], [FLAGS['BAC-02']])
        self.assertEqual(self.client.get('/api/users/1').json['username'], 'alex')
        self.assertEqual(self.client.get('/api/users/1').json['name'], 'Alex Morgan')
        response = self.mutate('/api/users/2', {'name': 'Alex Morgan'})
        self.assertEqual(response.json['changed_fields'], [])
        self.assertNotIn('flags', response.json)
        response = self.mutate('/api/users/1', {})
        self.assertEqual(response.json['user']['id'], 1)
        self.assertEqual(response.json['changed_fields'], [])
        self.assertEqual(response.json['user']['email'], 'alex@common.test')
        self.assertNotIn('password', response.json['user'])

    def test_unknown_roles_and_malformed_emails_are_rejected(self):
        for data in [{'role': ''}, {'role': 'administrator'}, {'email': '@'},
                     {'email': 'a@@common.test'}, {'email': 'a b@common.test'}, {'email': 'a@'}]:
            with self.subTest(data=data):
                self.assertEqual(self.mutate('/api/users/1', data).status_code, 400)
        self.assertEqual(self.client.get('/api/users/1').json['role'], 'member')
        self.assertEqual(self.client.get('/api/users/1').json['email'], 'alex@common.test')
        # Validation must not accidentally repair the intended privilege escalation.
        response = self.mutate('/api/users/1', {'role': 'admin'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(FLAGS['BAC-03'], response.json['flags'])

    def test_profile_email_uniqueness_is_case_insensitive(self):
        response = self.mutate('/api/users/1', {'email': ' MAYA@COMMON.TEST '})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.get('/api/users/1').json['email'], 'alex@common.test')
        response = self.mutate('/api/users/1', {'email': ' NEW@COMMON.TEST '})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/users/1').json['email'], 'new@common.test')

    def test_signup_rejects_case_variant_email_and_invalid_email(self):
        guest = self.app.test_client()
        guest.get('/signup')
        with guest.session_transaction() as session:
            csrf = session['csrf']
        for email in [' ALEX@COMMON.TEST ', '@', 'a@@common.test', 'a b@common.test']:
            with self.subTest(email=email):
                response = guest.post('/signup', data={'csrf': csrf, 'username': 'newneighbor',
                    'name': 'New Neighbor', 'email': email, 'password': 'neighbor-pass'})
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'role="alert"', response.data)
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM users').fetchone()[0], 5)

    def test_signup_duplicate_race_returns_form_error_not_traceback(self):
        guest = self.app.test_client()
        guest.get('/signup')
        with guest.session_transaction() as session:
            csrf = session['csrf']

        def register_competing_user(_password):
            with closing(sqlite3.connect(self.database)) as db:
                db.execute('INSERT INTO users (username,name,email,password) VALUES (?,?,?,?)',
                           ('racinguser', 'Other Registration', 'race@common.test', 'test-only-hash'))
                db.commit()
            return 'test-only-hash'

        with patch('app.generate_password_hash', side_effect=register_competing_user):
            response = guest.post('/signup', data={'csrf': csrf, 'username': 'racinguser',
                'name': 'New Neighbor', 'email': 'race@common.test', 'password': 'neighbor-pass'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'already in use', response.data)
        self.assertNotIn(b'Traceback', response.data)
        self.assertEqual(guest.get('/').status_code, 302)

    def test_malformed_signed_session_does_not_crash_or_select_a_user(self):
        for user_id in [[], {}, True, 1.0, '1']:
            with self.subTest(user_id=user_id):
                guest = self.app.test_client()
                with guest.session_transaction() as session:
                    session['user_id'] = user_id
                    session['csrf'] = 'valid-test-csrf'
                self.assertEqual(guest.get('/api/users/1').status_code, 401)
                self.assertEqual(guest.get('/').status_code, 302)
        with self.client.session_transaction() as session:
            session['csrf'] = 42
        self.assertEqual(self.client.get('/settings').status_code, 200)
        with self.client.session_transaction() as session:
            self.assertIsInstance(session['csrf'], str)
        self.assertEqual(self.mutate('/api/users/1', {'bio': 'Still works'}).status_code, 200)

    def test_comment_and_message_authors_have_stable_identity(self):
        self.mutate('/api/users/4', {'name': 'Alex Morgan'})
        comment = self.client.get('/api/posts/1/comments').json[0]
        self.assertEqual(comment['name'], 'Alex Morgan')
        self.assertEqual(comment['user_id'], 4)
        self.assertEqual(comment['username'], 'nia')
        message = self.client.get('/api/conversations/1').json['messages'][0]
        self.assertEqual(message['sender_id'], 2)
        self.assertEqual(message['username'], 'maya')

    def test_avatar_uses_whitespace_separated_name_parts(self):
        self.mutate('/api/users/1', {'name': 'Alex\tMorgan'})
        self.assertIn(b'aria-hidden="true">AM</span>', self.client.get('/settings').data)

    def test_head_requests_do_not_award_content_disclosure_flags(self):
        for path in ['/api/users/2', '/api/posts/7', '/posts/7', '/api/posts/7/comments',
                     '/api/conversations/2', '/ops/common.env.bak', '/api/staff/reports',
                     '/api/search?limit=banana']:
            with self.subTest(path=path):
                response = self.client.head(path)
                self.assertEqual(response.data, b'')
                self.assertNotIn('X-Lab-Flags', response.headers)
        self.assertEqual(self.client.get('/api/users/2').json['flags'], [FLAGS['INFO-01']])


if __name__ == '__main__':
    unittest.main()
