"""Normal resource browsing and conversation creation contracts."""
import tempfile
import unittest
from pathlib import Path

from app import create_app


class ResourceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.temp.name) / 'test.sqlite3')})
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session['user_id'] = 1
            session['csrf'] = 'test-token'

    def post(self, data):
        return self.client.post('/api/conversations', json=data, headers={'X-CSRF-Token': 'test-token'})

    def test_collections_filter_and_render(self):
        feed = self.client.get('/api/posts?view=cards')
        self.assertEqual(feed.status_code, 200)
        self.assertTrue(all(post['visibility'] == 'public' for post in feed.json['posts']))
        self.assertIn('href="/posts/4"', feed.json['html'])
        self.assertNotIn('X-Lab-Flags', feed.headers)
        profile = self.client.get('/api/users/2/posts?view=cards')
        self.assertEqual([post['id'] for post in profile.json['posts']], [1])
        self.assertEqual(self.client.get('/api/users/999/posts').status_code, 404)
        self.assertEqual(self.client.get('/api/posts?tab=saved').json['posts'], [])
        self.assertEqual(self.client.get('/api/posts/1?view=cards').json['posts'][0]['id'], 1)

    def test_user_collection_is_public_and_searchable(self):
        users = self.client.get('/api/users?q=maya').json['users']
        self.assertEqual(len(users), 1)
        self.assertEqual(users[0]['username'], 'maya')
        self.assertNotIn('email', users[0])
        self.assertNotIn('password', users[0])

    def test_start_read_reply_and_reuse(self):
        existing = self.post({'user_id': 2})
        self.assertEqual(existing.status_code, 200)
        self.assertEqual(existing.json['id'], 1)
        created = self.post({'user_id': 3})
        self.assertEqual(created.status_code, 201)
        thread_id = created.json['id']
        self.assertNotIn('X-Lab-Flags', created.headers)
        self.assertEqual(self.post({'user_id': 3}).json['id'], thread_id)
        listed = self.client.get('/api/conversations').json['conversations']
        self.assertEqual({thread['id'] for thread in listed}, {1, thread_id})
        read = self.client.get(f'/api/conversations/{thread_id}')
        self.assertEqual(read.json['messages'], [])
        self.assertNotIn('X-Lab-Flags', read.headers)
        reply = self.client.post(f'/api/conversations/{thread_id}', json={'body': 'Hello!'}, headers={'X-CSRF-Token': 'test-token'})
        self.assertEqual(reply.json['messages'][0]['body'], 'Hello!')
        with self.client.session_transaction() as session:
            session['user_id'] = 3
        self.assertIn(thread_id, [thread['id'] for thread in self.client.get('/api/conversations').json['conversations']])

    def test_creation_validation_and_auth(self):
        for value in [1, True, '2', None]:
            self.assertEqual(self.post({'user_id': value}).status_code, 400)
        self.assertEqual(self.post({'user_id': 999}).status_code, 404)
        self.assertEqual(self.client.post('/api/conversations', json={'user_id': 3}).status_code, 400)
        guest = self.app.test_client()
        for path in ['/api/posts', '/api/users', '/api/users/2/posts', '/api/conversations']:
            self.assertEqual(guest.get(path).status_code, 401)
