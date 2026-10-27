# Courier read path

nemik:W1049, caused by W1047, which linux-sources:W395 waits on. **Discovery only: no code, no
egress, no token read.** It builds on `docs/inbox-as-issues.md` (W728); the letter-to-issue
table there is assumed.

## The question

Which route may nemik read a repo's own letters by, as issues, without a sibling path and
without a credential on disk?

## What was found (read-only, 2026-10-27)

`gh auth status` on this host reports one login, `mikemol` on github.com, token held in the
system keyring (not a file), git protocol https, scopes `gist`, `read:org`, `repo`, `workflow`.
Nothing else was read: no token value was printed, no issue was listed, no request was sent
beyond the status check.

## Routes

| Route | Needs | Verdict |
|---|---|---|
| **A. the `gh` CLI as a subprocess** (`gh api repos/<owner>/<repo>/issues` with label filters) | the keyring login above; the `repo` scope reads private repos' issues | **Recommended.** nemik never sees the token: `gh` reads the keyring and nemik reads the JSON it prints. The login is already the operator's provisioning. |
| B. an API token the operator stores sealed, passed in the environment | an operator step to create and seal it, and a reader that unseals it | The fallback for the pod, which has no `gh` login (W728 "Offline and the pod"). A read-only fine-grained token would do; `repo` is broader than a read needs. Blocked on `operator: act` until wanted. |
| C. an unauthenticated read | nothing | Public repos only, and rate-limited to 60 an hour per address. Useless for the private fleet. |

Route A also carries the stated limits: `gh` is a binary the host must have (the pod does not),
and its keyring unlock is an interactive-session matter, so a tick that finds it locked must
answer "stale" and not wait (the offline rule of `read_queue`).

## What the reader would do (design, no code)

1. Resolve this repo's `<owner>/<repo>` from its git remote, once, as data.
2. Call route A for open issues labelled `kind:*` (the label vocabulary of W728), conditional on
   the last etag so an unchanged list costs no quota.
3. Read the repo's visibility at call time and never cache it (W728 egress rule). A read of
   one's own repo needs no releasable mark; only sending to a public repo does.
4. Return each issue as the activity W728 step 2 defines, with its `cites` label, and keep the
   `UNCLAIMED` rule of `nemik-inbound` unchanged: an issue is claimed when a waypoint cites its
   URL or its `cites` label.
5. On any failure (no `gh`, locked keyring, offline, rate limit) return the last good list marked
   stale with its age, within a stated time bound.

## What this leaves open

- Whether the host's `gh` login is the operator's blessed read route or only a convenience. It is
  the operator's own account, so reading one's own repos is not new disclosure, but the choice of
  route A over B is the operator's to confirm if they want the pod served the same way.
  I still need to put that to the operator as `operator: decide route A (gh keyring) or B
  (sealed read-only token)`, and have not, because route A needs no new credential and the
  reader is off by default.
- The etag cache's home (a file under the repo's cache directory, holding no secret).
- Rate budget across the fleet read, which touches every repo each tick (W728).

## Next, smallest first

1. Review of this note by linux-sources (the reader's first consumer) and the operator.
2. The pure activity parse, with a recorded `gh api` JSON as the fixture: no network.
3. The route-A transport behind the `Inbox` interface of W728 step 3, off by default.

W1048 (the send path) stays after this and needs an explicit go before anything is sent.

## The send path's credential route (read-only, 2026-10-27, W1048)

Read with `gh auth status`, which prints the login and scopes and does not use the token: the host
is logged in to github.com as the operator's account `mikemol`, token held in the keyring, with
scopes `gist`, `read:org`, `repo` and `workflow`. The `repo` scope covers creating an issue in a
private repo of that account, so route A (the gh keyring) is an authenticated write route on this
host with no new credential, and no key material is written to disk or held by a session. Whether
the permission applies was answered on W1047's warrant (the operator, 2026-10-19: private repos are
equivalent to their own account for egress). What is not read: a repo-scoped fine-grained token or
a sealed one (route B), and whether the pod can reach the keyring (not read; this route is the host's, and a
pod send would need route B). The YubiKey is never opened. Nothing has been sent; the first send is a deliberate
step of its own.
