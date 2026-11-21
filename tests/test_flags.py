"""Discovery flags confirm specific teaching flaws, not ordinary app activity."""
import tempfile
import unittest
from pathlib import Path

from app import create_app
from lab import FLAGS


class FlagTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.temp.name) / 'flags.sqlite3'), 'SECRET_KEY': 'flag-test-key'})
        self.client = self.app.test_client()
        self.login(self.client, 'alex', 'alex-common-2026')

    def login(self, client, username, password):
        client.delete_cookie('session')
        client.get('/login')
        with client.session_transaction() as session:
            csrf = session['csrf']
        self.assertEqual(client.post('/login', data={'csrf': csrf, 'username': username, 'password': password}).status_code, 302)
        client.get('/')

    def mutate(self, path, method='post', data=None):
        with self.client.session_transaction() as session:
            csrf = session['csrf']
        return getattr(self.client, method)(path, json=data or {}, headers={'X-CSRF-Token': csrf})

    def assert_flags(self, response, *exercises):
        expected = [FLAGS[exercise] for exercise in exercises]
        actual = response.headers.get('X-Lab-Flags', '')
        self.assertEqual(actual, ', '.join(expected))
        if response.is_json and isinstance(response.json, dict):
            self.assertEqual(response.json.get('flags', []), expected)
        return response

    def test_information_disclosure_flags(self):
        guest = self.app.test_client()
        for path, exercise in [('/ops/common.env.bak', 'INFO-02')]:
            with self.subTest(path=path):
                response = self.assert_flags(guest.get(path), exercise)
                self.assertIn(FLAGS[exercise].encode(), response.data)
        response = self.assert_flags(self.client.get('/api/users/2'), 'INFO-01')
        self.assertEqual(response.json['email'], 'maya@common.test')
        response = self.assert_flags(self.client.get('/api/search?limit=banana'), 'INFO-03')
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Flag found', response.data)
        self.assertIn(FLAGS['INFO-03'].encode(), response.data)
        self.assertIn(b'ValueError', response.data)

    def test_private_post_read_and_html_flag(self):
        response = self.assert_flags(self.client.get('/posts/6'), 'BAC-01')
        self.assertIn(FLAGS['BAC-01'].encode(), response.data)
        self.assertIn(b'Flag found', response.data)
        self.assert_flags(self.client.get('/api/posts/7'), 'BAC-01')
        self.assert_flags(self.client.get('/api/posts/6/comments'))  # Empty list alone proves no content disclosure.
        response = self.assert_flags(self.client.get('/api/posts/7/comments'), 'BAC-01')
        self.assertIsInstance(response.json, list)
        self.assertIn('COMMON-FUND-072', response.json[0]['body'])
        for action in ['like', 'save']:
            self.assert_flags(self.mutate('/api/posts/6/' + action), 'BAC-01')
        self.assert_flags(self.mutate('/api/posts/6/comments', data={'body': 'Not invited'}), 'BAC-01')

    def test_profile_mutations_require_real_changes(self):
        self.assert_flags(self.mutate('/api/users/2', 'patch', {'bio': 'Changed by another member'}), 'BAC-02')
        self.assert_flags(self.mutate('/api/users/2', 'patch', {'bio': 'Changed by another member'}))
        self.assert_flags(self.mutate('/api/users/2', 'patch', {}))
        self.assert_flags(self.mutate('/api/users/2', 'patch', {'ignored': 'value'}))
        self.assert_flags(self.mutate('/api/users/2', 'patch', {'role': 'admin'}), 'BAC-02', 'BAC-03')
        self.assert_flags(self.mutate('/api/users/1', 'patch', {'role': 'admin'}), 'BAC-03')
        self.assertEqual(self.client.get('/staff').status_code, 200)
        self.assert_flags(self.mutate('/api/users/1', 'patch', {'role': 'admin'}))

    def test_unauthorized_delete_and_chat(self):
        deleted = self.assert_flags(self.mutate('/api/posts/1', 'delete'), 'BAC-04')
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json['deleted_post'], {'id': 1, 'user_id': 2})
        self.assertEqual(self.client.get('/api/posts/1').status_code, 404)
        self.assert_flags(self.mutate('/api/posts/1', 'delete'))
        self.assert_flags(self.client.get('/api/conversations/2'), 'BAC-05')
        response = self.assert_flags(self.mutate('/api/conversations/2', data={'body': 'An uninvited reply'}))
        self.assertEqual(response.status_code, 403)
        self.assertNotIn('An uninvited reply', str(self.client.get('/api/conversations/2').json))

    def test_delete_flag_uses_current_role_not_original_login_role(self):
        # A student may already have completed the role-escalation exercise.
        self.assert_flags(self.mutate('/api/users/1', 'patch', {'role': 'admin'}), 'BAC-03')
        admin_delete = self.assert_flags(self.mutate('/api/posts/2', 'delete'))
        self.assertEqual(admin_delete.status_code, 200)
        self.assertEqual(admin_delete.json['deleted_post'], {'id': 2, 'user_id': 3})
        self.assert_flags(self.mutate('/api/users/1', 'patch', {'role': 'member'}))
        self.assert_flags(self.mutate('/api/posts/3', 'delete'), 'BAC-04')
        self.assert_flags(self.mutate('/api/posts/4', 'delete'))  # Own post.

    def test_staff_api_preserves_array_contract(self):
        response = self.assert_flags(self.client.get('/api/staff/reports'), 'BAC-06')
        self.assertIsInstance(response.json, list)
        self.assertEqual(response.json[0]['status'], 'open')
        self.assert_flags(self.mutate('/api/staff/reports/1/resolve'), 'BAC-06')
        self.assert_flags(self.mutate('/api/staff/reports/1/resolve'))
        response = self.assert_flags(self.mutate('/api/staff/reports/99999/resolve'))
        self.assertEqual(response.status_code, 404)

    def test_reconnaissance_is_not_a_graded_exploit(self):
        self.assertEqual(len(FLAGS), 9)
        self.assertNotIn('RECON-01', FLAGS)
        self.assertNotIn('INFO-04', FLAGS)
        guest = self.app.test_client()
        for client in [guest, self.client]:
            for path in ['/robots.txt', '/api/internal/health', '/ops/']:
                with self.subTest(path=path):
                    response = self.assert_flags(client.get(path))
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn(b'COMMON{', response.data)
        self.assertIn(b'/ops/', guest.get('/robots.txt').data)
        self.assertIn('backup', guest.get('/api/internal/health').json)

    def test_normal_usage_does_not_leak_flags(self):
        for path in ['/', '/?tab=saved', '/settings', '/people/alex', '/people/maya', '/messages', '/posts/1', '/api/users/1', '/api/posts/1', '/api/conversations/1', '/api/posts/1/comments', '/api/search?q=maya', '/staff', '/missing']:
            with self.subTest(path=path):
                response = self.assert_flags(self.client.get(path))
                self.assertNotIn(b'COMMON{', response.data)
        self.assert_flags(self.mutate('/api/users/1', 'patch', {'bio': 'My own edit'}))
        self.assert_flags(self.mutate('/api/posts/1/like'))
        self.assert_flags(self.mutate('/api/posts/1/save'))
        self.assert_flags(self.mutate('/api/posts/4', 'delete'))
        result = self.mutate('/api/posts', data={'body': 'My private note', 'visibility': 'private'})
        post_id = result.json['id']
        self.assert_flags(result)
        self.assert_flags(self.client.get(f'/api/posts/{post_id}'))
        self.assertNotIn(b'COMMON{', self.client.get(f'/posts/{post_id}').data)

    def test_errors_and_missing_objects_never_award(self):
        self.assert_flags(self.client.post('/api/posts/1/like', json={}))
        for path in ['/api/users/9999', '/api/posts/9999', '/posts/9999', '/api/conversations/9999']:
            self.assert_flags(self.client.get(path))
        for path, method, data in [('/api/users/2', 'patch', {'name': ''}), ('/api/users/2', 'patch', {'email': 'alex@common.test'}), ('/api/posts/6/comments', 'post', {'body': ' '}), ('/api/conversations/2', 'post', {'body': ' '}), ('/api/posts/9999/save', 'post', {})]:
            with self.subTest(path=path):
                response = self.assert_flags(self.mutate(path, method, data))
                self.assertGreaterEqual(response.status_code, 400)
        guest = self.app.test_client()
        self.assert_flags(guest.get('/api/users/2'))
        self.assert_flags(guest.get('/api/staff/reports'))

    def test_normal_admin_operations_do_not_award(self):
        self.login(self.client, 'ellis', 'ellis-common-2026')
        for path in ['/staff', '/api/staff/reports', '/api/users/2', '/api/internal/health']:
            self.assert_flags(self.client.get(path))
        self.assert_flags(self.mutate('/api/staff/reports/1/resolve'))
        self.assert_flags(self.mutate('/api/users/2', 'patch', {'bio': 'An admin edit'}))
        self.assert_flags(self.mutate('/api/posts/1', 'delete'))


if __name__ == '__main__':
    unittest.main()
