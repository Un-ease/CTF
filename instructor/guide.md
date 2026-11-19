# Instructor guide — spoilers

Keep this file and the repository away from student-facing web hosting. Flask serves only explicit routes and `static/`; the Docker build copies neither this guide nor the tests.

## Teaching intent

Start with passive discovery, map the app as an ordinary member, record a normal request in a proxy, then vary one identifier or field at a time. Emphasize the difference between authentication, object-level authorization, and function/field-level authorization. All people, messages, amounts, codes, and addresses are fictional.

No SQL injection, command execution, file upload, server-side fetching, or executable debug console is intentionally provided. SQL values are parameterized, template output is escaped, JS builds user content with `textContent`, passwords are hashed, and state-changing requests need CSRF tokens. This keeps early sessions focused on recon, information disclosure, and BAC rather than unrelated injection noise. These boundaries are not a security guarantee: the application is deliberately compromised by design.

## Accounts

| Username | Password | Role | User ID |
| --- | --- | --- | --- |
| alex | alex-common-2026 | member | 1 |
| maya | maya-studio-2026 | member | 2 |
| jules | jules-film-2026 | member | 3 |
| nia | nia-garden-2026 | member | 4 |
| ellis | ellis-common-2026 | admin | 5 |

Give students Alex's account or let them register. A second member account can be provided for differential testing. Do not hand out the admin credentials initially.

## Real-world grounding

See [`real-world-cases.md`](real-world-cases.md) for the source-backed mapping of every graded exercise, prerequisites, differences from the original disclosures, and the changes made after review. These are simplified analogues of documented product vulnerabilities, **not exact CVE reproductions**. Flags and data are fictional.

## Exercise and reconnaissance catalog

| ID | Surface | Reproduction as Alex | Evidence / impact | Intended repair |
| --- | --- | --- | --- | --- |
| RECON-01 (ungraded) | Headers and robots | Inspect `X-Powered-By`, then `/robots.txt` | Framework/version fingerprint and hidden path discovery | Minimize stack details; robots is not access control |
| INFO-01 | Profile API | `GET /api/users/2` | Maya's email is returned although settings promise it isn't public | Serialize explicit public fields, return private fields only to owner |
| INFO-02 | Operational backup | `/robots.txt` → `/ops/` → `/ops/common.env.bak` | Actual lab signing key, database path, internal API location | Keep backups outside served paths, deny operational artifacts, rotate exposed keys |
| INFO-03 | Search diagnostics | `GET /api/search?q=maya&limit=banana` | 500 page with Python traceback, source path, source line, storage path | Validate input; return generic errors and log diagnostics privately |
| INFO-04 (ungraded recon) | Internal health | `GET /api/internal/health` without login | Release, environment, database path, backup path | Restrict diagnostics; public health returns minimal status |
| BAC-01 | Private post reads | Compare feed/profile with `/posts/6`, `/api/posts/6`, `/api/posts/7` | Non-public launch code `4826` and `COMMON-FUND-072` financial draft | Enforce visibility on every object read, including comments/reactions |
| BAC-02 | Profile modification | Capture own settings PATCH, change URL from `/api/users/1` to `/api/users/2` | Alex can edit Maya's bio/email | Verify ownership before update; role-aware policy for delegated changes |
| BAC-03 | Field-level access | Add `"role":"admin"` to Alex's profile PATCH | Persistent role change unlocks `/staff` on the next request | Use a member-editable field allowlist that excludes privileged properties |
| BAC-04 | Post deletion | Capture own delete, replace ID with `1` (Maya's post) | Another author's post disappears | Author/admin policy on deletion; return 403/404 on denial |
| BAC-05 | Direct messages | Inbox shows only conversation 1; request `/api/conversations/2` or `/3` | Read other members' messages; uninvited POST is correctly rejected with 403 | Apply the existing write membership check to reads too |
| BAC-06 | Staff API | `/staff` gives 403, but `/api/staff/reports` works; POST `/api/staff/reports/1/resolve` | Ordinary member reads/resolves moderation reports | Centralize staff role enforcement on all staff routes, not just HTML |
| CHAIN-01 | Session integrity | Recover INFO-02 key; sign a Flask cookie with `user_id:5` | Impersonate Ellis and access staff UI without changing a role | Rotate compromised key, remove artifacts, invalidate sessions; consider revocable server-side sessions |

The direct post, comment, like, and save APIs share missing visibility checks. Treat those as additional manifestations of BAC-01 rather than inflating the count with duplicate findings.

## Beginner discovery flags

The app now surfaces **9 static teaching flags** only at the relevant discovery surfaces. Share `STUDENT.md` with learners; keep this answer key private. No flag catalog is exposed by a route or shipped in browser JavaScript. Backend definitions live in `lab.py`.

| Exercise | Flag | Award condition |
| --- | --- | --- |
| INFO-01 | `COMMON{private_email_public_response}` | A non-admin member reads another user's profile API |
| INFO-02 | `COMMON{backups_are_not_public_assets}` | Read the exposed environment backup |
| INFO-03 | `COMMON{tracebacks_tell_secrets}` | Trigger the deliberate invalid-search-limit ValueError |
| BAC-01 | `COMMON{a_hidden_post_is_not_a_locked_post}` | Read another author's non-public post or a nonempty comment response, or successfully change comments/reactions through a direct endpoint |
| BAC-02 | `COMMON{your_session_someone_elses_profile}` | A non-admin successfully changes another user's stored profile values |
| BAC-03 | `COMMON{member_to_admin_with_one_field}` | A non-admin successfully changes a user's role from another value to `admin` |
| BAC-04 | `COMMON{not_your_post_to_delete}` | A non-admin successfully deletes someone else's existing post |
| BAC-05 | `COMMON{not_a_member_still_in_the_chat}` | Read a conversation without participant membership; uninvited writes are not an exercise |
| BAC-06 | `COMMON{staff_api_without_staff_role}` | A non-admin reads the staff API or changes an existing unresolved report to resolved |

Flags appear in JSON objects under `flags` and in the `X-Lab-Flags` response header. Existing JSON arrays stay unchanged, so use the header for comments and staff-report lists. Successful HTML discoveries show a selectable **Flag found** banner; the diagnostic page does too. The backup includes its flag in the text body. `robots.txt` and the health metadata are ungraded reconnaissance clues, not flag-bearing exploits. The shared browser API helper turns flag headers into the same banner. The banner is page-local, not persistent progress tracking.

No-op updates, failed validation/CSRF, missing objects, ordinary owner operations, and legitimate administrative account/moderation operations do not earn those mutation flags. Multiple profile flaws can produce multiple flags in the same response. Perform member-only exercises before escalating privileges, or reset between them. Reading a hidden post as its owner does not award BAC-01. An empty hidden-comment list is not evidence of a content disclosure and earns no read flag. Fresh fixtures include a private comment on post 7; existing databases are not changed automatically.

**CHAIN-01 has no separate token.** It builds on the INFO-02 flag; require the member/forged-cookie comparison and successful `/staff` request as proof. This stateless signed-cookie app cannot reliably distinguish a valid forged admin cookie from a legitimately issued one, so simply awarding a chain flag on every admin page would be misleading.

These flags are intentionally static and source-readable. They are learning feedback, not tamper-resistant grading or proof of who performed an exploit. Require a reproducible report, not just the token.

## Baseline behavior (not exercises)

Normal workflows should remain usable: mobile sign-out is visible, new posts sort newest first, timestamps come from stored creation times (UTC), and authors can find their own saved non-public posts. Deleting a post removes its related comments, likes, saves, and moderation reports; unauthorized deletion itself remains BAC-04.

JSON write endpoints require objects with text fields. Invalid profile names/emails/role values return 400, case-insensitive duplicate account emails return 409, and missing profile IDs return 404. The only supported roles are `member` and `admin`; a member can still assign `admin` through BAC-03. Registration also handles a duplicate-insert race with a form error instead of an accidental traceback. These validation checks do **not** enforce ownership or remove role mass assignment. Search's invalid-limit traceback remains the deliberate INFO-03 diagnostic exercise. Registration trims names before validation so a whitespace prefix cannot create an unusable account.

Profile PATCH responses identify the actual updated account in `user` and list `changed_fields`; they do not merge request or session identity into that record. Owner responses include the saved email, while other-target PATCH responses omit it so an empty PATCH does not become another ungraded email leak. A display name can differ from the immutable username, including after BAC-02. The settings UI updates its own name/avatar immediately, warns on an unexpected target, and comments/messages show usernames beside display names. Test with separate accounts rather than assuming equal names imply equal identities.

HEAD requests do not award disclosure flags: an empty HEAD response is not proof that private content was delivered. Ordinary GET disclosures and all nine exercises remain graded. Malformed session field types are handled without accidental database/type exceptions; the documented correctly signed session-forgery chain still works.

## Request practice

Use a proxy to preserve the session cookie and the `X-CSRF-Token` header. The token is in `<meta name="csrf-token">` on signed-in pages. A 400 from an absent/stale token is not an authorization fix: replay with the member's valid token.

For a quick instructor reproduction, sign in as Alex and run in that page's browser console:

```js
const csrf = document.querySelector('meta[name="csrf-token"]').content;
const change = (path, method, body = {}) => fetch(path, {
  method,
  headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
  body: JSON.stringify(body)
}).then(r => r.json());

// Horizontal access: edit someone else's account.
await change('/api/users/2', 'PATCH', {bio: 'Updated by another member'});

// Vertical access: change a field not offered in the settings form.
await change('/api/users/1', 'PATCH', {role: 'admin'});
// Visit /staff after this request.

// Missing function-level authorization; works even before role escalation.
await change('/api/staff/reports/1/resolve', 'POST');
```

The default key is intentionally easy to find in source, but students should only receive HTTP access. Setting `SECRET_KEY` via the environment changes the key leaked by the backup too: the session-forgery chain remains real, not a fake flag.

Session-forgery demonstration (instructor shell with Flask installed):

```python
from flask import Flask
app = Flask(__name__)
app.secret_key = 'KEY_RECOVERED_FROM_THE_LAB_BACKUP'
serializer = app.session_interface.get_signing_serializer(app)
print(serializer.dumps({'user_id': 5, 'csrf': 'classroom-proof'}))
```

Set the printed value as the `session` cookie on this lab's origin. `/staff` should now load. Do not use any real application's key or cookies.

## Suggested sequence

1. **Recon:** no hints beyond the app URL. Inventory routes, cookies, HTTP headers, assets, IDs, robots, and response differences.
2. **Disclosure:** distinguish a harmless version string from sensitive data; find the backup and error page. Ask students to describe a credible chain rather than simply screenshot a stack trace.
3. **Horizontal BAC:** use two member accounts; compare list/detail behavior, change user/post/conversation IDs, show one read and one write impact.
4. **Vertical BAC:** test a staff function as a member. Then test the profile update body for privileged fields.
5. **Chain:** connect backup disclosure to signed-session impersonation. Explain why CSRF and password hashing do not repair a compromised signing key.
6. **Repair session:** implement one server-side authorization policy, invert the relevant vulnerable-behavior tests, and check for alternate endpoints that still bypass it.

Ask for a report with the account/role used, original request, changed request, minimal response evidence, impact, and a server-side fix. Keep deletion exercises until the end, or assign separate instances.

## Isolation and operation

- Dedicated disposable VM/container only; no production data, mounts, credentials, email service, or cloud permissions. Containerization alone is not a complete boundary.
- Keep host binding on `127.0.0.1`; use an authenticated VPN/SSH tunnel for authorized students. Don't publish it unauthenticated to the internet.
- Compose denies container egress via its internal network. Apply host firewall policy too. Never mount the Docker socket or a home directory.
- Start one worker so first-run fixture creation is deterministic. Multiple parallel first-run processes are not supported.
- Stop the server before resets. Reset replaces the DB, not the signing key or already-issued cookies.
- All dependencies install at build time. Fonts and illustrations are local; the running UI needs no third-party CDN.

## Next feature ideas

Add believable functionality first, then its lesson: invitations (token scope), groups (nested-resource authorization), account exports (download ownership), media attachments (metadata disclosure), notification preferences (method-specific authorization). Add a numbered catalog entry and a regression test for each new trust boundary. Keep solutions and challenge selectors out of the student UI.
