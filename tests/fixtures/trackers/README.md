# Recorded tracker issues (nemik:W956, under W369 and W370)

Two real, public issues as their trackers' APIs returned them, kept byte for byte so a typed reader
(W957) and the mirror plan (W958) are tested against the shape a tracker really sends, not a shape
written from memory. Nothing in them was edited. Both are public data fetched without a token.

| File | Fetched from | When | Notes |
|---|---|---|---|
| `github_issue.json` | `GET https://api.github.com/repos/cli/cli/issues/2000` | 2026-10-24 | an open issue with three labels (`enhancement`, `gh-repo`, `help wanted candidate`), a nested `user`, the usual `*_url` fields |
| `forgejo_issue.json` | `GET https://codeberg.org/api/v1/repos/forgejo/forgejo/issues/1` | 2026-10-24 | a closed issue with no labels, `milestone: null`, `assignees: null`, a nested `user` and `repository`; Forgejo's issue API is Gitea's |

What the two show that a reader has to cope with, read from the files:

- The same idea has different keys: GitHub's state is `"open"` or `"closed"` and its issue link is
  `html_url`; Forgejo has `html_url` too but also `is_locked` where GitHub has `locked`, and the
  number is `number` in both.
- GitHub's issues endpoint also returns pull requests (an issue whose `html_url` says `pull`, as
  `cli/cli#1` does); a reader that mirrors issues must say what it does with those.
- Labels are a list of objects on both, and may be empty. Forgejo's `assignees` and `milestone` may be
  `null`.
- GitHub's issue carries `issue_dependencies_summary` (`blocked_by`, `total_blocked_by`, `blocking`,
  `total_blocking`, here all 0) and `sub_issues_summary`: counts only, not the issues themselves, so
  a mirror that wants nemik's blocked-on edges on GitHub has to read the dependency endpoints
  separately. This fixture does not show them.
- The files hold third parties' public usernames and, for Forgejo's deleted-user placeholder, a
  `noreply` address. They are test data, not something nemik sends anywhere.
