# Real-world grounding review — instructor only

## What this document claims

Common is a **fictional, simplified teaching application**, not a reproduction of any company's code or a vulnerable version of the products below. Its **nine graded exercises** model failure modes documented in real products. Flags and fictional records are classroom instrumentation, not secrets from real incidents.

A published vulnerability is not automatically a confirmed malicious breach. The source may describe a researcher demonstration or vendor-discovered flaw. Do not tell students that every case was exploited against real victims. Likewise, do not copy a source CVSS score onto this lab: prerequisites, data sensitivity, and impact differ.

These nine exercises are **not nine unrelated vulnerability classes**. Several are read/write manifestations of missing authorization. Require the request, permission boundary, observed impact, and remediation—not merely a token or a CWE label.

## Review summary

| Lab exercise | Documented case | Shared failure mode | Important difference |
| --- | --- | --- | --- |
| INFO-01: private email in profile JSON | Mattermost, CVE-2022-0708 | An API returns a private email to an authenticated user who should not receive it | Mattermost's case concerns the team creator's email; Common uses a member profile serializer |
| INFO-02: exposed environment backup | Laravel-related CVE-2017-16894 | An exposed environment file discloses operational secrets | The CVE has a specific environment-file-permissions cause; Common deliberately serves a backup route |
| INFO-03: verbose search exception | Ajenti, CVE-2018-1000083 | Malformed input produces a traceback containing an internal server path | Ajenti's input was login JSON; Common uses a logged-in search limit |
| BAC-01: hidden post available through another read surface | Flarum, CVE-2023-22488 | Visibility checks on one surface do not protect all paths to the same private content | Flarum leaked through email notifications; Common leaks through direct HTML/JSON/comment endpoints |
| BAC-02: another member's profile can be edited | Kanboard, CVE-2017-15199 | An authenticated user changes another user's private object's metadata | Kanboard's object was a project; Common's is a user profile |
| BAC-03: privileged property accepted in an update | GitHub's March 2012 public-key incident | Insufficient control of accepted update parameters crosses a privilege boundary | GitHub's case attached a key to an organization; Common accepts a `role` property |
| BAC-04: deleting another member's post | Facebook Graph API album-deletion disclosure by Laxman Muthiyah | A valid attacker credential plus a victim object ID permits unauthorized deletion | The original required a Facebook mobile-app token and an album ID; Common uses a member session and post ID |
| BAC-05: reading another conversation | Rocket.Chat, CVE-2022-32220 | A message-reading method fails to enforce room membership | The original method was `getUserMentionsByChannel`; Common uses a direct conversation GET |
| BAC-06: member reaches a staff API | Cisco DCNM, CVE-2020-3112 | A low-privileged authenticated account can invoke an API with administrative privileges | Common's moderation API is a simplified analogue, not Cisco's crafted request or exact endpoint |

**Classification:** all rows are same-failure-mode/class analogues. None is advertised as an exact CVE reproduction. BAC-01 in particular is an alternate-read-surface analogy, not evidence that Flarum had Common's numeric-post-ID endpoint.

## Sources and evaluation notes

### INFO-01 — Mattermost private-email disclosure

- [Vendor-authored CVE record, CVE-2022-0708](https://www.cve.org/CVERecord?id=CVE-2022-0708)
- [CVE record JSON](https://cveawg.mitre.org/api/cve/CVE-2022-0708)
- [Mattermost security updates](https://mattermost.com/security-updates/)

The vendor record describes authenticated team members obtaining the team creator's private email through an API. Common's account settings explicitly promise that email is not displayed on a public profile. Compare an ordinary profile page with another user's profile API. The email returned—not knowing a numeric ID—is the disclosure evidence. Do not claim account takeover from this email-only exercise.

### INFO-02 — Environment-file exposure

- [CVE-2017-16894](https://www.cve.org/CVERecord?id=CVE-2017-16894)
- [CVE record JSON and its scope qualification](https://cveawg.mitre.org/api/cve/CVE-2017-16894)

The record describes disclosure through `/.env` in Laravel through 5.5.21 and explicitly narrows its cause to `writeNewEnvironmentFileWith` using `file_put_contents` without restricting permissions. It does **not** mean every Laravel installation exposes `.env`, nor that a URL named `.env` is inherently vulnerable.

Common substitutes an intentionally served `.env.bak` artifact. The disclosed signing key is actually used by the lab. A fake key that cannot affect authentication would not demonstrate the claimed chain. Do not claim Laravel's precise filesystem bug exists in this Flask app.

### INFO-03 — Traceback disclosure

- [CVE-2018-1000083](https://www.cve.org/CVERecord?id=CVE-2018-1000083)
- [CVE record JSON](https://cveawg.mitre.org/api/cve/CVE-2018-1000083)

The Ajenti record specifically describes malformed login JSON returning a traceback that leaks a server path. Common intentionally returns a real Python traceback for an invalid search limit. This is a **limited information-disclosure lesson**, not automatic RCE or proof of exposed credentials. A generic 500 without internal details should not earn the flag. Real programs may classify a path-only disclosure as low severity or informational.

### BAC-01 — Visibility enforced inconsistently

- [Flarum's advisory, GHSA-8gcg-vwmw-rxj4 / CVE-2023-22488](https://github.com/flarum/framework/security/advisories/GHSA-8gcg-vwmw-rxj4)

Flarum's advisory explains that listed alerts used a visibility check while email notifications could still carry restricted content. Its exploit prerequisites include the relevant subscription/notification behavior; Common does not reproduce those features.

The transferable lesson is that filtering a feed does not authorize every other content read. In Common, use the author's **private post 7** as the clearest comparison. The `circle` label is simplified: this app does not implement a social graph, so do not pretend to demonstrate a real friend-list implementation. Comments only earn a read flag when an actual comment is returned, not for an empty list. A seeded private reviewer comment gives this alternate endpoint meaningful fictional evidence.

### BAC-02 — Unauthorized object editing

- [CVE-2017-15199](https://www.cve.org/CVERecord?id=CVE-2017-15199)
- [Kanboard's referenced fix](https://github.com/kanboard/kanboard/commit/074f6c104f3e49401ef0065540338fc2d4be79f0)

The record describes authenticated users altering form data to edit another user's private project metadata, including Name, Email, Identifier, and Description. Common changes the resource type to a profile and the transport to JSON PATCH. Require a before/after comparison proving a stored value changed. A 200 response to a no-op or nonexistent target is insufficient.

### BAC-03 — Privileged-field update / mass-assignment pattern

- [GitHub: Public Key Security Vulnerability and Mitigation, March 4, 2012](https://github.blog/news-insights/the-library/public-key-security-vulnerability-and-mitigation/)

GitHub's own incident report says a user added a public key to the Rails organization and pushed a file as a demonstration. It identifies unchecked incoming form parameters as a mass-assignment vulnerability.

Common does not run Rails or use an automatic ORM binder. Its deliberately over-broad update allowlist simulates the same field-level trust failure by accepting `role`. Demonstrate persistent privilege gain and access to `/staff`, not merely that the request body contains `admin`.

### BAC-04 — Unauthorized deletion

- [Laxman Muthiyah: Deleting any photo albums — How I Hacked Your Facebook Photos](https://thezerohack.com/how-i-hacked-your-facebook-photos)

The researcher describes a successful Graph API DELETE using his own Facebook-for-Android token and another user's album ID, and reports Facebook's fix. The current page carries a later publication/republishing timestamp; do not infer an incident date from that timestamp alone.

Common's attacker is an ordinary member deleting another member's post. It does not reproduce Facebook's mobile-app token distinction. Require that the target existed beforehand and is gone afterward. Use fictional fixtures; perform deletion exercises last.

### BAC-05 — Private-message reads without membership

- [CVE-2022-32220](https://www.cve.org/CVERecord?id=CVE-2022-32220)
- [CNA record JSON](https://cveawg.mitre.org/api/cve/CVE-2022-32220)
- [Researcher disclosure referenced by the CNA](https://hackerone.com/reports/1410246)

The record says Rocket.Chat before v5 disclosed private-channel and direct messages through `getUserMentionsByChannel` regardless of room access permission. This supports a **read-disclosure** exercise.

Common previously also allowed uninvited message injection. That extra behavior was not established by this source, so POST now checks membership and rejects a nonparticipant with 403. GET deliberately remains vulnerable and returns the flag with the disclosed conversation. Never describe this as a faithful implementation of Rocket.Chat's Meteor method.

### BAC-06 — Function-level API authorization

- [Cisco advisory: DCNM privilege escalation](https://sec.cloudapps.cisco.com/security/center/content/CiscoSecurityAdvisory/cisco-sa-20200219-dcnm-priv-esc)
- [Vendor-authored CVE-2020-3112 record](https://www.cve.org/CVERecord?id=CVE-2020-3112)

Cisco describes insufficient REST API access-control validation allowing a low-privileged authenticated user to interact with administrative privileges. The vendor record states PSIRT was not aware of malicious use at publication; this is not evidence of a confirmed breach.

Common uses a staff-page role gate contrasted with an API that only requires login. That UI/API contrast is a teaching simplification, not a claim about Cisco's UI. Reading protected reports or changing an existing unresolved report proves the lab impact.

## Supplemental chain: a known signing key can defeat session integrity

- [Apache's CVE-2023-27524 announcement](https://www.openwall.com/lists/oss-security/2023/04/24/2)
- [Apache-authored CVE record](https://www.cve.org/CVERecord?id=CVE-2023-27524)
- [CISA Known Exploited Vulnerabilities entry](https://www.cisa.gov/known-exploited-vulnerabilities-catalog?field_cve=CVE-2023-27524)

Apache Superset through 2.0.1 could permit unauthorized authentication on installations retaining its default `SECRET_KEY`. The key signs session cookies. Common uses Flask signed sessions too, so this is a close technical analogue for what happens **after** the lab key is known.

The original key source was an unchanged default, not Common's exposed backup. Common deliberately combines two known failure modes: environment-secret disclosure and session forgery. It does not claim that Superset had this backup route or that RCE is implemented here. No separate chain token is awarded because a stateless app cannot reliably distinguish a correctly forged cookie from a legitimately signed one; grade the comparison and staff access as evidence.

## Changes made after review

1. Removed the `robots.txt` flag. Reading published crawl instructions is reconnaissance, not exploitation.
2. Removed the health-metadata flag. A version, release, or storage path alone does not establish a sensitive-data or privilege boundary violation. These remain breadcrumbs; this is not a simulation of an exposed Spring Actuator environment or command endpoint.
3. Limited BAC-05 to unauthorized reads and enforced membership on writes, matching the scope supported by its source.
4. Stopped awarding a hidden-comment read flag for an empty response. Added a fictional private reviewer comment to fresh fixtures so an actual disclosure can be demonstrated.
5. Kept flag names and fictional stories separate from the historical sources. There are no real victim records or live-company targets in the lab.

Existing databases are not automatically reset or populated with the new private comment. The direct private-post read still works; reset a disposable classroom instance if you want the new fixture. **A reset destroys existing edits and registrations.**

## Instructor evaluation checklist

- Can the learner show the legitimate behavior and the unauthorized comparison using accounts they control or approved fixtures?
- Is there actual private content, a stored unauthorized edit, deletion, or privileged function—not just an unusual status code?
- Does the explanation identify the missing server-side boundary rather than calling sequential IDs a vulnerability by themselves?
- Does the learner distinguish authentication from authorization, and disclosure from takeover/RCE?
- Can they explain one material difference between the lab and the cited real-world case?
- Would enforcing the proposed repair on every relevant endpoint stop the exploit while preserving normal use?

To add an exercise, first record a source and its actual prerequisites/impact here, label any simplifications, then write positive and negative regression tests. Test **only the isolated lab**, not the historical products or their hosted services.
