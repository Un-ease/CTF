# Common — your first security investigation

Your instructor will give you the lab URL and an account. Test **only that lab**. All its people and data are fictional. Do not scan other sites or the hosting machine.

## How you know you found something

This beginner edition has **9 discovery flags**, formatted as `COMMON{...}`. You do not need to guess them.

- Some appear in a **Flag found** banner after an unexpected action succeeds.
- Some are in a JSON response's **`flags`** field or in a plain-text file.
- API responses also put discovered flags in the **`X-Lab-Flags`** response header. List-shaped responses use this header instead of changing their normal format.

To inspect a response in your browser: open Developer Tools → **Network**, perform the action again, select the request, and look at **Response** and **Headers**. Your instructor can also show you how to capture a request in a testing proxy.

The banner shows discoveries from the current page; it is **not a saved scoreboard**. Copy each flag into your notes before navigating away.

## What to submit

For each finding, save:

1. The flag.
2. Which account you used.
3. The request: method, URL, and changed fields. Do not share your password or session cookie.
4. The relevant response or a screenshot.
5. What should have happened versus what actually happened.
6. Why it matters and one idea for fixing it.

A strange error alone is not always a vulnerability. Public paths, sequential IDs, version numbers, and health metadata are clues—not automatically bugs, and they do not earn flags on their own. A flag is a classroom confirmation; the request and explanation are your evidence.

The exercises are simplified analogues of publicly documented vulnerabilities in real products. The people, records, and flag strings are fictional; this is not an exact recreation of those products or permission to test them. Your instructor can share the historical case studies after you submit your findings.

## Ground rules

- Start by using the application normally. Understand your own profile, posts, and messages first.
- Work as an ordinary member. If you gain extra privileges, record it, then ask your instructor whether to reset before continuing.
- Leave destructive actions until the end; deleting data may remove another exercise's evidence.
- Do not change another student's account or data. Use separate instances or only the instructor-approved fictional accounts.
- Flags are shared teaching markers, not anti-cheat certificates. A copied flag without a reproduction is not a completed report.
