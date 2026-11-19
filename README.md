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
docker compose up --build -d
```

Stop a running local server first if it already occupies port 5000. Compose uses a non-root container, a read-only root filesystem, a writable data volume, dropped capabilities, resource limits, an internal network, and a host-loopback-only published port. Gunicorn runs the application without an interactive debugger.

For remote classes, put this on a **disposable VM**, restrict access using a private VPN or SSH tunnel and firewall, and give students only the app's HTTP endpoint—not the repository, host filesystem, or Docker socket. Keep the loopback binding. An example student tunnel is:

```sh
ssh -L 5000:127.0.0.1:5000 instructor@classroom-vm
```

Students then browse `http://127.0.0.1:5000`. Do not add a gateway that rewrites the app's session cookie or strips the diagnostic responses: those are teaching surfaces. Use one instance per student/group when possible, since destructive authorization exercises affect shared data.

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
- People search and editable account/profile details
- Seeded direct-message conversations with working replies
- Staff report queue and resolution actions
- Centered desktop feed, prioritized neighborhood sidebar, and labeled mobile bottom navigation
- Grouped profile settings, readable local timestamps, keyboard skip link, reduced-motion support, and locally hosted fonts/illustrations

“Close circle” is an audience label for the initial access-control exercises, not a fully implemented social graph. There is no follow system, message initiation UI, email delivery, media upload, or password-recovery service yet. No external services are required at runtime.

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
- `instructor/guide.md`: exercise catalog and answer key
- `instructor/real-world-cases.md`: verified historical sources, scope differences, and evaluation criteria

For each new bug: document a real-world source and its scope first, add a believable feature, choose one broken trust boundary, add fictional evidence to the fixtures, document reproduction/impact/fix privately, and write a test proving the bug exists. Recreate the database after schema changes; this first version has no migrations.
