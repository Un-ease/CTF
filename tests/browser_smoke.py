"""Optional real-browser smoke test; uses disposable storage, not the classroom DB."""
import os
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
from app import create_app


def main():
    with tempfile.TemporaryDirectory() as temp:
        app = create_app({'DATABASE': str(Path(temp) / 'browser.sqlite3')})
        server = make_server('127.0.0.1', 0, app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        errors = []
        external = []
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH', '/usr/bin/chromium'), headless=True)
                page = browser.new_page(viewport={'width': 1440, 'height': 1080}, device_scale_factor=1)
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('request', lambda req: external.append(req.url) if not req.url.startswith(origin) else None)
                page.goto(origin)
                page.get_by_label('Username', exact=True).fill('alex')
                page.get_by_label('Password', exact=True).fill('alex-common-2026')
                page.locator('.auth-form button').click()
                page.wait_for_url(origin + '/')
                page.get_by_role('heading', name='Around here.').wait_for()
                assert page.locator('#lab-discoveries').is_hidden(), 'Normal browsing must not reveal flags'
                page.goto(origin + '/posts/6')
                page.get_by_text('COMMON{a_hidden_post_is_not_a_locked_post}', exact=True).wait_for()
                assert page.locator('#lab-discoveries').is_visible()
                page.goto(origin)
                page.evaluate('''async () => {
                    const reports = await api('/api/staff/reports');
                    if (!Array.isArray(reports)) throw new Error('Flag broke the staff report array');
                }''')
                page.get_by_text('COMMON{staff_api_without_staff_role}', exact=True).wait_for()
                page.goto(origin)
                assert page.locator('#lab-discoveries').is_hidden()
                page.evaluate('document.fonts.ready')
                page.locator('.post-art img').evaluate_all('images => images.forEach(image => image.loading = "eager")')
                page.wait_for_function('Array.from(document.images).every(image => image.complete && image.naturalWidth > 0)')
                page.screenshot(path='/tmp/common-desktop.png', full_page=True, animations='disabled')
                page.get_by_role('button', name='Like post', exact=True).first.click()
                page.get_by_role('button', name='Save post', exact=True).first.click()
                page.get_by_role('link', name='Saved posts', exact=True).click()
                page.locator('.post').first.wait_for()
                page.get_by_role('link', name='Home feed', exact=True).click()
                page.locator('#post-body').fill('Browser-tested and feeling neighborly.')
                page.get_by_role('button', name='Post', exact=True).click()
                page.get_by_text('Browser-tested and feeling neighborly.', exact=True).wait_for()
                page.locator('.show-comments').first.click()
                comment = page.locator('.comment-form').first
                comment.get_by_role('textbox').fill('A real browser reply')
                comment.get_by_role('button', name='Reply').click()
                page.locator('.comment-list p').filter(has_text='A real browser reply').wait_for()
                page.locator('#search').fill('Maya')
                page.locator('#search').press('Enter')
                with page.expect_response(origin + '/api/users/2') as profile_response:
                    page.locator('#search-results a').first.click()
                page.get_by_role('heading', name='Maya Chen', exact=True).wait_for()
                page.wait_for_load_state('networkidle')
                assert profile_response.value.json()['email'] == 'maya@common.test'
                assert profile_response.value.json()['flags'] == ['COMMON{private_email_public_response}']
                assert profile_response.value.headers['x-lab-flags'] == 'COMMON{private_email_public_response}'
                assert page.locator('#lab-discoveries').is_hidden(), 'Passive profile load announced an exploit flag'
                page.get_by_role('link', name='Settings', exact=True).click()
                page.locator('input[name="name"]').fill('  Alex Updated  ')
                page.get_by_label('About you', exact=True).fill('Updated from a real browser.')
                page.get_by_role('button', name='Save changes').click()
                page.get_by_role('status').filter(has_text='Changes saved').wait_for()
                assert page.locator('.account strong').text_content() == 'Alex Updated', 'Sidebar identity stayed stale after saving'
                assert page.locator('.settings-avatar strong').text_content() == 'Alex Updated'
                assert page.locator('.account small').text_content() == '@alex', 'Display-name edit changed the account identity'
                assert page.locator('.top-avatar .avatar').text_content() == 'AU'
                assert page.locator('input[name="name"]').input_value() == 'Alex Updated', 'Form did not apply server-normalized values'
                # Simulate a proxy changing the PATCH target: never merge that user into our sidebar.
                page.route('**/api/users/1', lambda route: route.fulfill(json={
                    'ok': True, 'user': {'id': 2, 'username': 'maya', 'name': 'Different Account'},
                    'changed_fields': ['name']
                }))
                page.locator('input[name="name"]').fill('Submitted Name')
                page.get_by_role('button', name='Save changes').click()
                page.get_by_role('status').filter(has_text='not your signed-in account').wait_for()
                assert page.locator('.account strong').text_content() == 'Alex Updated'
                assert page.locator('.settings-avatar strong').text_content() == 'Alex Updated'
                page.unroute('**/api/users/1')
                page.reload()
                assert page.get_by_label('About you', exact=True).input_value() == 'Updated from a real browser.'
                assert page.locator('input[name="name"]').input_value() == 'Alex Updated'
                page.locator('nav a[href="/messages"]').click()
                page.locator('.thread').first.click()
                page.get_by_label('Your message', exact=True).fill('See you at the market!')
                page.get_by_role('button', name='Send').click()
                page.get_by_text('See you at the market!', exact=True).wait_for()
                assert '@maya' in page.locator('#message-list strong').first.text_content(), 'Message author lacks stable username'
                assert '@alex' in page.locator('#message-list strong').last.text_content()
                page.set_viewport_size({'width': 390, 'height': 844})
                page.goto(origin)
                page.locator('.post-art img').evaluate_all('images => images.forEach(image => image.loading = "eager")')
                page.wait_for_function('Array.from(document.images).every(image => image.complete && image.naturalWidth > 0)')
                page.screenshot(path='/tmp/common-mobile.png', full_page=True, animations='disabled')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile layout overflows'
                sign_out = page.get_by_role('button', name='Sign out', exact=True)
                assert sign_out.is_visible(), 'Mobile users must be able to sign out'
                sign_out.click()
                page.wait_for_url(origin + '/login')
                assert page.locator('.account').count() == 0
                page.go_back()
                page.wait_for_url(origin + '/login')
                assert page.locator('.account').count() == 0, 'Back navigation restored a logged-out identity'
                page.goto(origin + '/settings')
                page.wait_for_url(origin + '/login')
                page.goto(origin + '/signup')
                page.get_by_label('Your name', exact=True).fill('Browser Neighbor')
                page.get_by_label('Email', exact=True).fill('browser@common.test')
                page.get_by_label('Username', exact=True).fill('browserneighbor')
                page.get_by_label('Password', exact=True).fill('browser-neighbor-2026')
                page.locator('.auth-form button').click()
                page.wait_for_url(origin + '/')
                assert page.locator('.account strong').text_content() == 'Browser Neighbor'
                page.goto(origin + '/login')
                page.wait_for_url(origin + '/')
                page.locator('#post-body').fill('Only my private bookmark.')
                page.get_by_label('Post audience', exact=True).select_option('private')
                page.get_by_role('button', name='Post', exact=True).click()
                page.wait_for_url(origin + '/people/browserneighbor')
                page.get_by_role('button', name='Save post', exact=True).click()
                page.get_by_role('status').filter(has_text='Saved for another day').wait_for()
                page.locator('nav a[href="/?tab=saved"]').click()
                page.get_by_text('Only my private bookmark.', exact=True).wait_for()
                page.goto(origin + '/messages')
                page.evaluate('''async () => {
                    const originalFetch = window.fetch;
                    const pending = {};
                    window.fetch = path => new Promise(resolve => {
                        pending[path] = subject => resolve({
                            ok: true, headers: new Headers(), json: async () => ({subject, messages: []})
                        });
                    });
                    try {
                        const first = loadConversation('1');
                        const second = loadConversation('2');
                        pending['/api/conversations/2']('Latest selection');
                        await second;
                        pending['/api/conversations/1']('Stale selection');
                        await first;
                        if (document.querySelector('#conversation-title').textContent !== 'Latest selection') {
                            throw new Error('Stale conversation response replaced the latest selection');
                        }
                    } finally { window.fetch = originalFetch; }
                }''')
                # Exercise breakpoint edges and real pages, not only the feed.
                page.emulate_media(reduced_motion='reduce')
                for width in [320, 375, 700, 701, 768, 1024, 1440, 1920]:
                    page.set_viewport_size({'width': width, 'height': 900})
                    for path in ['/', '/?tab=saved', '/settings', '/messages', '/people/browserneighbor', '/people/maya', '/posts/1']:
                        page.goto(origin + path)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}px: {path}'
                        assert page.locator('main').count() == 1, f'Missing main landmark: {path}'
                    page.goto(origin)
                    if width >= 1440:
                        post = page.locator('.post').first.bounding_box()
                        composer = page.locator('.composer').bounding_box()
                        heading = page.locator('.page-heading').bounding_box()
                        sidebar = page.locator('.sidebar').bounding_box()
                        assert post['width'] <= 640, 'Desktop feed stretched beyond reading width'
                        assert abs(post['x'] - heading['x']) <= 1, 'Feed and heading gutters do not align'
                        assert post['x'] >= sidebar['x'] + sidebar['width'] + 32, 'Feed touches the sidebar'
                        assert composer['height'] <= 180, 'Desktop composer is oversized'
                    nav = page.get_by_role('navigation', name='Main navigation')
                    assert nav.get_by_role('link', name='Home feed', exact=True).get_attribute('aria-current') == 'page'
                    if width <= 700:
                        box = nav.bounding_box()
                        assert box and box['y'] > 780, 'Mobile navigation is not at the bottom'
                        assert nav.get_by_role('link').count() == 5
                        assert page.get_by_role('button', name='Sign out', exact=True).is_visible()
                    page.get_by_label('Find people', exact=True).fill('Maya')
                    page.get_by_role('button', name='Search people', exact=True).click()
                    page.locator('#search-results a').first.wait_for()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Search overflows at {width}px'
                page.set_viewport_size({'width': 390, 'height': 844})
                page.goto(origin)
                page.evaluate('document.fonts.ready')
                page.screenshot(path='/tmp/common-mobile-viewport.png', animations='disabled')
                page.set_viewport_size({'width': 1440, 'height': 1080})
                page.goto(origin + '/settings')
                page.evaluate('document.fonts.ready')
                page.screenshot(path='/tmp/common-settings.png', full_page=True, animations='disabled')
                page.goto(origin)
                page.keyboard.press('Tab')
                assert page.locator('.skip-link').evaluate('element => element === document.activeElement'), 'Skip link must be the first keyboard stop'
                page.keyboard.press('Enter')
                assert page.evaluate('document.activeElement.id') == 'main-content', 'Skip link did not focus content'
                page.goto(origin + '/settings')
                # User-controlled profile text must not push the layout sideways.
                page.evaluate('''async () => {
                    const id = document.querySelector('#settings-form').dataset.id;
                    await api('/api/users/' + id, 'PATCH', {
                        name: 'A'.repeat(80), bio: 'B'.repeat(500), location: 'C'.repeat(100)
                    });
                }''')
                for width in [320, 768, 1440]:
                    page.set_viewport_size({'width': width, 'height': 900})
                    for path in ['/', '/settings', '/people/browserneighbor']:
                        page.goto(origin + path)
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Long profile text overflows at {width}px: {path}'
                # Expire the cookie while a signed-in page remains open.
                csrf = page.locator('meta[name="csrf-token"]').get_attribute('content')
                page.request.post(origin + '/logout', headers={'X-CSRF-Token': csrf})
                page.locator('#search').fill('Maya')
                page.get_by_role('button', name='Search people', exact=True).click()
                page.wait_for_url(origin + '/login')
                assert page.locator('.account').count() == 0, 'Expired API session left another identity on screen'
                guest = browser.new_page(viewport={'width': 320, 'height': 844})
                for path in ['/login', '/signup']:
                    guest.goto(origin + path)
                    assert guest.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Guest page overflow: {path}'
                    assert guest.locator('.auth-form').is_visible()
                guest.close()
                page.goto(origin + '/login')
                page.get_by_label('Username', exact=True).fill('alex')
                page.get_by_label('Password', exact=True).fill('alex-common-2026')
                page.locator('.auth-form button').click()
                page.wait_for_url(origin + '/')
                page.goto(origin + '/people/jules')
                page.wait_for_function('!document.querySelector("[data-post-source]").hasAttribute("aria-busy")')
                page.get_by_role('link', name='Open post', exact=True).first.click()
                page.wait_for_url(origin + '/posts/2')
                page.goto(origin + '/people/jules')
                page.get_by_role('button', name='Message', exact=True).click()
                page.wait_for_url('**/messages?conversation=*')
                page.locator('#conversation-content').wait_for(state='visible')
                page.get_by_label('Your message', exact=True).fill('Hello from your profile!')
                page.get_by_role('button', name='Send').click()
                page.locator('#message-list').get_by_text('Hello from your profile!', exact=True).wait_for()
                conversation_url = page.url
                page.goto(origin + '/people/jules')
                page.get_by_role('button', name='Message', exact=True).click()
                page.wait_for_url(conversation_url)
                page.locator('#message-list').get_by_text('Hello from your profile!', exact=True).wait_for()
                page.goto(origin)
                page.wait_for_function('!document.querySelector("[data-post-source]").hasAttribute("aria-busy")')
                for width in [320, 390, 1440]:
                    page.set_viewport_size({'width': width, 'height': 1080})
                    assert page.evaluate('''() => {
                        const heading = document.querySelector('#post-4 .post-heading');
                        const person = heading.querySelector('.person').getBoundingClientRect();
                        const controls = heading.querySelector('.post-controls').getBoundingClientRect();
                        const buttons = [...heading.querySelectorAll('.post-controls > *')].map(el => el.getBoundingClientRect());
                        return person.right <= controls.left && buttons[0].right <= buttons[1].left;
                    }'''), f'Post controls overlap at {width}px'
                # Model an intercepting proxy changing an own-post DELETE to another ID.
                def change_delete_target(route):
                    response = route.fetch(url=origin + '/api/posts/1')
                    assert response.json()['flags'] == ['COMMON{not_your_post_to_delete}']
                    assert response.headers['x-lab-flags'] == 'COMMON{not_your_post_to_delete}'
                    route.fulfill(response=response)
                page.route('**/api/posts/4', change_delete_target)
                page.once('dialog', lambda dialog: dialog.accept())
                page.locator('#post-4 .delete-post').click()
                page.get_by_text('COMMON{not_your_post_to_delete}', exact=True).wait_for()
                page.locator('#post-1').wait_for(state='detached')
                assert page.locator('#post-4').count() == 1, 'Changed request removed the wrong card'
                page.unroute('**/api/posts/4')
                assert not errors, errors
                assert not external, external
                browser.close()
                print('Browser smoke passed: feed, likes, saves, posts, comments, search, settings, messages, mobile logout, signup identity, private bookmarks, conversation race, live identity updates, cross-account response isolation, expired sessions, HTML/API discovery flags, 8 responsive widths, desktop reading measure, search dropdowns, reduced motion; no JS errors or external requests.')
        finally:
            server.shutdown()
            thread.join()


if __name__ == '__main__':
    main()
