# Common

A fictional neighborhood social network for an evolving web-security classroom. Ordinary app on the surface; deliberately broken trust boundaries underneath. No challenge menu or advance solutions in the UI; beginner discovery flags appear when a teaching flaw is exercised.

**Run only as an isolated lab.** Do not put it directly on the public internet, connect real services, reuse real credentials, or store real personal data. The operational-artifact route deliberately exposes the app's real *lab-only* session signing key. Instructor documentation is not served by Flask and is excluded from the container image.

## Run locally

Python 3.11+:

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Open **http://127.0.0.1:5000**. A SQLite database and fictional fixtures are created on first start. The local `python app.py` entry point reloads edited templates without enabling Flask’s debugger; restart it after Python changes.

Student account: **`alex` / `alex-common-2026`**. Students can also register normally. Other accounts and exercise solutions are in [`instructor/guide.md`](instructor/guide.md).

## Run in a container

```sh
docker compose up --build -d --wait
```

Open **http://127.0.0.1:15000**. Use `docker-compose` instead if your machine has the standalone Compose executable. Set `LAB_PORT` to choose another host port.

The application has **no published port** and stays on an internal-only network. An unprivileged, read-only NGINX proxy publishes `127.0.0.1:15000`, preserving cookies, diagnostic responses, and flag headers. It waits for the application health check and re-resolves the backend after container replacement. Only the proxy also joins the ingress bridge; the vulnerable backend has no direct egress. Gunicorn runs without an interactive debugger. Both containers drop capabilities and have resource limits.

This avoids macOS AirPlay's port 5000 and Docker configurations that do not activate published ports for internal-only containers. It does not affect other applications on ports 443 or 8799.

### Upgrading the earlier manual proxy setup

The proxy is now included in `compose.yaml` and `deploy/lab-proxy.conf`. After pulling, back up the old machine-local override so it does not replace the maintained health dependency or proxy configuration:

```sh
if [ -f compose.override.yaml ]; then
  mv compose.override.yaml "compose.override.yaml.backup-$(date +%Y%m%d-%H%M%S)"
fi
docker-compose up --build -d --wait
curl -I http://127.0.0.1:15000/
```

Expect a 302 redirect to `/login`. Do **not** use `down -v` or reset the database just to update the application. The existing `common-data` volume and account edits remain intact.

For remote classes, put this on a **disposable VM**, restrict access using a private VPN or SSH tunnel and firewall, and give students only the app's HTTP endpoint—not the repository, host filesystem, or Docker socket. Keep the loopback binding. An example student tunnel is:

```sh
ssh -N -L 15000:127.0.0.1:15000 lab-tunnel@classroom-vm
```

Use a forwarding-only SSH account rather than granting students shell/repository access. Students then browse `http://127.0.0.1:15000`.

For Tailscale, use **Serve**, not Funnel:

```sh
tailscale serve --bg --https=8443 http://127.0.0.1:15000
```

Share the HTTPS URL printed by Tailscale only with approved tailnet users. Restrict student access to the lab's port; sharing a host that already serves other applications must not grant access to those applications. A dedicated lab node is preferable. Do not add a gateway that rewrites the app's session cookie or strips the diagnostic responses: those are teaching surfaces. Use one instance per student/group when possible, since destructive authorization exercises affect shared data.

## Reset

Stop the app first, then restore its fixture database:

```sh
.venv/bin/flask --app app:create_app reset-db --yes
```

For Docker (stop first to avoid in-flight writes):

```sh
docker compose stop common
docker compose run --rm --no-deps common flask --app app:create_app reset-db --yes
docker compose up -d
```

This deletes **all** registrations and edits. Existing browser sessions remain valid against restored user IDs; sign out or clear cookies for a completely fresh exercise.

## Beginner flags

There are **9 discovery flags** in `COMMON{...}` format. Successful exploit responses expose them through a **Flag found** banner, JSON `flags`, plain-text artifacts, or the `X-Lab-Flags` response header. Normal account activity does not award exploit flags. There is no saved scoreboard; students should record each flag with a reproducible request and impact explanation.

Share [`STUDENT.md`](STUDENT.md) as the learner handout. The private flag answer key and precise conditions are in [`instructor/guide.md`](instructor/guide.md). Flags are static teaching feedback, not anti-cheat proof. Each graded exercise has a documented real-world analogue in [`instructor/real-world-cases.md`](instructor/real-world-cases.md), with explicit differences from the original case. `robots.txt` and health metadata are ungraded recon clues, not stand-alone exploits.

## What works

- Registration, sign-in, sign-out, persistent hashed passwords and cookie sessions
- Public feed; public, close-circle, and private posts; profile timelines
- Likes, comments, bookmarks, deleting posts, and saved feed
- People search and editable account/profile details, with explicit target IDs/usernames in update responses
- Live refresh of your own display name/avatar; comments and messages include stable usernames
- Seeded direct-message conversations with working replies
- Staff report queue and resolution actions
- Centered desktop feed, prioritized neighborhood sidebar, and labeled mobile bottom navigation
- Grouped profile settings, readable local timestamps, keyboard skip link, reduced-motion support, and locally hosted fonts/illustrations

“Close circle” is an audience label for the initial access-control exercises, not a fully implemented social graph. There is no follow system, message initiation UI, email delivery, media upload, or password-recovery service yet. No external services are required at runtime.

## Identity and shared lab data

`id` and `username` identify the account; `name` is an editable display name and is not unique. An account with `username: "alex"` can legitimately have a different display name after an edit—including the intentional unauthorized-edit exercise. GET profile responses read one database row; a GET body does not update or merge user fields.

Profile PATCH responses include the actual updated `user` and `changed_fields`. The UI only refreshes the signed-in identity when the returned target matches it; it explicitly warns when a different account was changed. Owner update responses also return the saved email, but another account's update response does not add a new email leak. Display-name changes never change usernames or account IDs.

Use one instance per student/group. Profile edits, role changes, and deletions persist and can affect other learners sharing an instance. Code updates do not restore altered names or roles. The Python entry point and container deployment use separate databases by default; make sure you are inspecting the same instance. Reset only when you intentionally want to destroy lab data.

## Verify

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js  # optional syntax check
```

Optional real-browser test (requires local Chromium):

```sh
.venv/bin/pip install -r requirements-dev.txt
CHROMIUM_PATH=/usr/bin/chromium .venv/bin/python tests/browser_smoke.py
```

The browser test uses temporary storage, checks real interactions, keyboard skip navigation, conversation response ordering, long profile text, and overflow across eight widths (320–1920px), desktop feed width/alignment, and rejects JavaScript errors/external requests. It writes screenshots to `/tmp/common-desktop.png`, `/tmp/common-mobile.png`, `/tmp/common-mobile-viewport.png`, and `/tmp/common-settings.png`. Backend tests exercise both normal behavior and intentional vulnerabilities; these tests should fail if a teaching flaw accidentally disappears.

## Extend

- `app.py`: routes, sessions, authorization decisions, diagnostic handling
- `db.py`: schema and repeatable fixtures
- `lab.py`: discovery flag definitions and response formatting
- `templates/`, `static/`: normal student-facing application
- `tests/test_app.py`: behavior and vulnerability regression tests
- `tests/test_flags.py`: flag awards and false-positive regression tests
- `tests/test_correctness.py`: accidental identity, validation, session, and response-contract regressions
- `deploy/lab-proxy.conf`: loopback ingress proxy configuration
- `instructor/guide.md`: exercise catalog and answer key
- `instructor/real-world-cases.md`: verified historical sources, scope differences, and evaluation criteria

For each new bug: document a real-world source and its scope first, add a believable feature, choose one broken trust boundary, add fictional evidence to the fixtures, document reproduction/impact/fix privately, and write a test proving the bug exists. Recreate the database after schema changes; this first version has no migrations.
