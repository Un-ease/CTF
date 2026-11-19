"""Regression tests cover normal workflows AND the intended teaching flaws."""
import tempfile
import unittest
from pathlib import Path

from app import create_app


class CommonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.temp.name) / 'test.sqlite3'), 'SECRET_KEY': 'test-signing-key'})
        self.client = self.app.test_client()
        self.client.get('/login')
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        response = self.client.post('/login', data={'username': 'alex', 'password': 'alex-common-2026', 'csrf': csrf})
        self.assertEqual(response.status_code, 302)
        self.client.get('/')

    def tearDown(self):
        self.temp.cleanup()

    def mutate(self, path, method='post', data=None):
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        return getattr(self.client, method)(path, json=data or {}, headers={'X-CSRF-Token': csrf})

    def test_pages_and_assets(self):
        for path in ['/', '/?tab=saved', '/people/alex', '/people/maya', '/settings', '/messages', '/posts/1', '/static/style.css', '/static/app.js', '/static/studio.svg', '/static/icons.svg']:
            with self.subTest(path=path):
                with self.client.get(path) as response:
                    self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/staff').status_code, 403)
        self.assertEqual(self.client.get('/people/nobody').status_code, 404)
        self.assertEqual(self.client.get('/posts/9999').status_code, 404)

    def test_auth_and_csrf_boundaries(self):
        guest = self.app.test_client()
        self.assertEqual(guest.get('/').status_code, 302)
        self.assertEqual(guest.get('/api/users/1').status_code, 401)
        self.assertEqual(guest.get('/api/conversations/2').status_code, 401)
        self.assertEqual(self.client.post('/api/posts', json={'body': 'No token'}).status_code, 400)
        self.mutate('/logout')
        self.assertEqual(self.client.get('/api/users/1').status_code, 401)

    def test_non_ascii_invalid_csrf_is_rejected_without_traceback(self):
        guest = self.app.test_client()
        guest.get('/login')
        response = guest.post('/login', data={'csrf': 'é', 'username': 'alex', 'password': 'wrong'})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b'TypeError', response.data)
        response = self.client.post('/api/posts', json={'body': 'Rejected'}, headers={'X-CSRF-Token': 'é'})
        self.assertEqual(response.status_code, 400)
        self.assertIsNotNone(response.json.get('error'))

    def test_guest_pages_never_show_account_identity(self):
        guest = self.app.test_client()
        for path in ['/', '/?tab=saved', '/people/alex', '/settings', '/messages', '/posts/1', '/staff', '/login', '/signup']:
            with self.subTest(path=path):
                response = guest.get(path, follow_redirects=True)
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'class="auth-form"', response.data)
                self.assertNotIn(b'class="account"', response.data)
                self.assertNotIn(b'Alex Morgan', response.data)

    def test_authenticated_auth_pages_redirect_to_feed(self):
        for path in ['/login', '/signup']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.location, '/')
                self.assertIn(b'Alex Morgan', self.client.get(path, follow_redirects=True).data)

    def test_logout_clears_identity_and_protected_pages(self):
        self.mutate('/logout')
        for path in ['/', '/settings', '/messages', '/people/alex']:
            with self.subTest(path=path):
                response = self.client.get(path, follow_redirects=True)
                self.assertIn(b'class="auth-form"', response.data)
                self.assertNotIn(b'Alex Morgan', response.data)
        self.assertEqual(self.client.get('/api/users/1').status_code, 401)

    def test_invalid_session_does_not_authenticate(self):
        guest = self.app.test_client()
        guest.set_cookie('session', 'invalid-cookie')
        self.assertEqual(guest.get('/').location, '/login')
        self.assertEqual(guest.get('/api/users/1').status_code, 401)
        with guest.session_transaction() as session:
            session['user_id'] = 99999
        self.assertEqual(guest.get('/').location, '/login')
        self.assertEqual(guest.get('/api/users/1').status_code, 401)

    def test_signup(self):
        guest = self.app.test_client()
        guest.get('/signup')
        with guest.session_transaction() as session:
            csrf = session['csrf']
        result = guest.post('/signup', data={'csrf': csrf, 'username': 'newneighbor', 'name': 'New Neighbor', 'email': 'new@common.test', 'password': 'neighbor-pass'})
        self.assertEqual(result.status_code, 302)
        self.assertIn(b'New Neighbor', guest.get('/people/newneighbor').data)
        self.assertNotIn(b'Alex Morgan', guest.get('/settings').data)

    def test_signup_normalizes_names_before_length_validation(self):
        guest = self.app.test_client()
        guest.get('/signup')
        with guest.session_transaction() as session:
            csrf = session['csrf']
        result = guest.post('/signup', data={'csrf': csrf, 'username': 'longname',
            'name': ' ' * 80 + 'Neighbor', 'email': 'long@common.test', 'password': 'neighbor-pass'})
        self.assertEqual(result.status_code, 302)
        self.assertEqual(guest.get('/').status_code, 200)
        self.assertIn(b'Neighbor', guest.get('/settings').data)

    def test_post_comment_like_save(self):
        result = self.mutate('/api/posts', data={'body': 'Hello neighborhood', 'visibility': 'public'})
        self.assertEqual(result.status_code, 201)
        post_id = result.json['id']
        self.assertIn(b'Hello neighborhood', self.client.get('/').data)
        self.assertTrue(self.mutate(f'/api/posts/{post_id}/like').json['active'])
        self.assertFalse(self.mutate(f'/api/posts/{post_id}/like').json['active'])
        self.mutate(f'/api/posts/{post_id}/save')
        self.assertIn(b'Hello neighborhood', self.client.get('/?tab=saved').data)
        result = self.mutate(f'/api/posts/{post_id}/comments', data={'body': 'A reply'})
        self.assertEqual(result.json[0]['body'], 'A reply')
        self.assertEqual(self.mutate('/api/posts', data={'body': ' '}).status_code, 400)

    def test_own_settings_and_messages(self):
        self.mutate('/api/users/1', 'patch', {'bio': 'New bio'})
        self.assertEqual(self.client.get('/api/users/1').json['bio'], 'New bio')
        result = self.mutate('/api/conversations/1', data={'body': 'See you Saturday'})
        self.assertEqual(result.json['messages'][-1]['body'], 'See you Saturday')

    def test_profile_validation_does_not_break_pages(self):
        for data in [{'name': ''}, {'name': '   '}, {'name': None}, {'email': 'invalid'}]:
            with self.subTest(data=data):
                self.assertEqual(self.mutate('/api/users/1', 'patch', data).status_code, 400)
                self.assertEqual(self.client.get('/').status_code, 200)
        self.assertEqual(self.mutate('/api/users/1', 'patch', {'email': 'maya@common.test'}).status_code, 409)
        self.assertEqual(self.mutate('/api/users/9999', 'patch', {'bio': 'Hello'}).status_code, 404)

    def test_json_objects_and_text_are_validated(self):
        with self.client.session_transaction() as session:
            headers = {'X-CSRF-Token': session['csrf']}
        for path, method in [('/api/users/1', 'patch'), ('/api/posts', 'post'),
                             ('/api/posts/1/comments', 'post'), ('/api/conversations/1', 'post')]:
            for payload in [[], 'text', 42]:
                with self.subTest(path=path, payload=payload):
                    self.assertEqual(getattr(self.client, method)(path, json=payload, headers=headers).status_code, 400)
        for path in ['/api/posts', '/api/posts/1/comments', '/api/conversations/1']:
            for body in [None, [], {}, 12]:
                with self.subTest(path=path, body=body):
                    self.assertEqual(self.mutate(path, data={'body': body}).status_code, 400)
        self.assertEqual(self.mutate('/api/posts', data={'body': 'Hello', 'visibility': []}).status_code, 400)

    def test_new_posts_first_and_own_private_bookmarks(self):
        result = self.mutate('/api/posts', data={'body': 'Newest public note'})
        page = self.client.get('/').data
        self.assertLess(page.index(f'id="post-{result.json["id"]}"'.encode()), page.index(b'id="post-1"'))
        self.assertIn(b'<time datetime=', page)
        self.assertNotIn(b'Yesterday', page)
        result = self.mutate('/api/posts', data={'body': 'My private bookmark', 'visibility': 'private'})
        self.mutate(f'/api/posts/{result.json["id"]}/save')
        self.assertIn(b'My private bookmark', self.client.get('/?tab=saved').data)
        self.mutate('/api/posts/7/save')
        self.assertNotIn(b'COMMON-FUND-072', self.client.get('/?tab=saved').data)

    def test_delete_cleans_up_related_data(self):
        from db import get_db
        self.mutate('/api/posts/4/save')
        self.mutate('/api/posts/4/like')
        self.assertEqual(self.mutate('/api/posts/4', 'delete').status_code, 200)
        with self.app.app_context():
            for table in ['likes', 'saves', 'comments', 'reports']:
                with self.subTest(table=table):
                    self.assertEqual(get_db().execute(f'SELECT count(*) FROM {table} WHERE post_id=4').fetchone()[0], 0)

    def test_bac01_hidden_posts_direct_access(self):
        feed = self.client.get('/').data
        self.assertNotIn(b'4826', feed)
        self.assertNotIn(b'COMMON-FUND-072', feed)
        self.assertNotIn(b'4826', self.client.get('/people/maya').data)
        self.assertIn(b'4826', self.client.get('/posts/6').data)
        self.assertIn('COMMON-FUND-072', self.client.get('/api/posts/7').json['body'])

    def test_bac02_other_user_update(self):
        self.mutate('/api/users/2', 'patch', {'bio': 'Changed by Alex'})
        self.assertEqual(self.client.get('/api/users/2').json['bio'], 'Changed by Alex')

    def test_bac03_role_mass_assignment(self):
        self.assertEqual(self.client.get('/staff').status_code, 403)
        self.mutate('/api/users/1', 'patch', {'role': 'admin'})
        self.assertEqual(self.client.get('/staff').status_code, 200)
        self.assertIn(b'Community desk', self.client.get('/').data)

    def test_bac04_delete_other_post(self):
        self.assertEqual(self.mutate('/api/posts/1', 'delete').status_code, 200)
        self.assertEqual(self.client.get('/api/posts/1').status_code, 404)

    def test_bac05_private_conversation(self):
        self.assertNotIn(b'data-id="2"', self.client.get('/messages').data)
        self.assertIn('STUDIO-GUEST-83', self.client.get('/api/conversations/2').json['messages'][0]['body'])
        result = self.mutate('/api/conversations/2', data={'body': 'Alex was not invited'})
        self.assertEqual(result.status_code, 403)
        self.assertNotIn('Alex was not invited', str(self.client.get('/api/conversations/2').json))

    def test_bac06_staff_api(self):
        self.assertEqual(self.client.get('/staff').status_code, 403)
        self.assertEqual(self.client.get('/api/staff/reports').json[0]['status'], 'open')
        self.mutate('/api/staff/reports/1/resolve')
        self.assertEqual(self.client.get('/api/staff/reports').json[0]['status'], 'resolved')

    def test_info_disclosure_chain(self):
        guest = self.app.test_client()
        self.assertIn(b'/ops/', guest.get('/robots.txt').data)
        self.assertIn(b'common.env.bak', guest.get('/ops/').data)
        self.assertIn(b'SECRET_KEY=test-signing-key', guest.get('/ops/common.env.bak').data)
        self.assertIn('test.sqlite3', guest.get('/api/internal/health').json['database'])
        self.assertEqual(self.client.get('/api/users/2').json['email'], 'maya@common.test')
        error = self.client.get('/api/search?limit=banana')
        self.assertEqual(error.status_code, 500)
        self.assertIn(b'ValueError', error.data)
        self.assertIn(b'app.py', error.data)

    def test_session_forgery_from_backup(self):
        # Confirms the exposed key is not a decorative fake.
        serializer = self.app.session_interface.get_signing_serializer(self.app)
        forged = serializer.dumps({'user_id': 5, 'csrf': 'instructor-token'})
        guest = self.app.test_client()
        guest.set_cookie('session', forged)
        self.assertEqual(guest.get('/staff').status_code, 200)

    def test_output_escaping(self):
        self.mutate('/api/posts', data={'body': '<script>alert(1)</script>'})
        page = self.client.get('/').data
        self.assertIn(b'&lt;script&gt;', page)
        self.assertNotIn(b'<script>alert(1)</script>', page)

    def test_reset(self):
        self.mutate('/api/posts/1', 'delete')
        result = self.app.test_cli_runner().invoke(args=['reset-db', '--yes'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.client.get('/api/posts/1').status_code, 200)


if __name__ == '__main__':
    unittest.main()
