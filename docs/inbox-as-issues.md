# The inbox without sibling paths

nemik:W728, answering mtools:W1710. **Design only: no code, no egress.**

## The ruling

The operator, 2026-10-19 (session 695f3e0a, warranted on W728):

- line 84035: repos should stop being aware that "sibling paths" exist at all; the inbox
  pattern may map to GitHub issues, public or private, and a private repo counts as the
  operator's own egress (it is theirs and not disclosed);
- line 84099: the issues-as-inbox idea maps to the ActivityPub and other open-standards stance
  nemik already orients around.

## What reaches across repos today

Two things read a sibling directory:

1. **Letters.** A letter is `<repo>/inbox/YYYY-MM-DD-<from>-<topic>.md`, first line
   `from -> to:`. `nemik-inbound`, `nemik-check --letters` and the fold plan read every
   repo's `inbox/` by path; an answered letter moves to `inbox/archive/`.
2. **Queues.** The fleet read (`nemik-rank`, `nemik-check`, the viewer's documents) opens each
   repo's `.claude/paths-forward.json` and ledger under `~/github/<repo>/`.

Code already arrives pinned (sha-pinned wheels); data can arrive pinned (a fetch at a ref,
as el-openglo's `luthen_pin.json` does). Letters and queues are the remaining sibling reach.

## The frame: actors, activities, transports

`docs/model.md` already lists "messages between workstreams" as ForgeFed / ActivityStreams,
designed and not implemented. The design is that layer, with the transport left open.

- **Actor.** Each workstream (repo) is an actor with an inbox and an outbox.
- **Activity.** A letter is an ActivityStreams activity from one actor to another. An ask is
  an `Offer` whose object is a ForgeFed `Ticket`; the answer is `Accept`, `Reject` or
  `Resolve`. The object cites its waypoint as `<repo>:W<n>`, the symbol both sides already
  use. A plain note is a `Note` addressed to the recipient. (ForgeFed's Ticket,
  TicketDependency and Resolve terms are as `docs/model.md` records them; whether the draft
  still names them so is unverified.)
- **Transport.** How an activity moves is an adapter, so no repo needs to know where another
  repo lives. The same activity can ride:
  - **A GitHub issue** on the recipient's repo (the first transport the operator named).
  - **A Forgejo ticket**, since the fleet's own Forgejo speaks ForgeFed natively; it may be
    the natural first transport for repos that live there.
  - **A file in `inbox/`**, the current form, kept as the fallback while the others land.

## A letter as a GitHub issue

| Letter today | Issue |
|---|---|
| file in the recipient's `inbox/` | an issue opened on the recipient's repo |
| first line `from -> to:` | labels `from:<repo>` and a `to` that is the repo itself |
| kind (ask, info, alert, reply) | label `kind:<kind>` |
| cited `<repo>:W<n>` | label `cites:<repo>:W<n>`, and the symbol in the first line of the body |
| the body | the issue body, markdown as now |
| reply | a comment; an answer that closes the matter closes the issue |
| archived (`inbox/archive/`) | a closed issue: nothing moves, nothing is deleted |
| "uncited and stale" (`--older-than`) | open, with no `cites` label that any queue also cites, older than N days: closed with a comment saying nothing cited it |

`nemik-inbound` would list open issues labelled `kind:*` on the repo through the API instead
of listing a directory; the `UNCLAIMED` rule is unchanged (no waypoint in the repo's queue
cites the issue's `cites` label or its URL). A waypoint cites an issue by its URL, in the
place it cites a letter path today.

## Egress

The operator counts a private repo as their own account. So:

- Letters between the operator's repos go only to private repos of theirs: no new disclosure.
- A letter to a public repo is disclosure. The adapter must refuse to open an issue on a
  public repo unless the letter is marked releasable, and say why when it refuses.
- No credential is written to disk by nemik: the API token comes from the environment the
  operator already provisions, and the YubiKey is never opened.
- Nothing is sent until this design is reviewed and a card says so.

## The queue read

Each repo's queue would be fetched at a pinned ref rather than opened from a sibling
directory: `(repo, ref) -> paths-forward.json`, ref a commit sha, so a fleet read names the
exact state it read and is repeatable. A moving ref (the default branch head) is allowed
only where the read says it is live. The ledger and the `inbox/` fold would be fetched the
same way. This is the harder half: the fleet read today is cheap because it is local.

## What this leaves unsolved

- **Latency and rate limits.** A directory read is free; an API read is not. The fleet read
  touches every repo's queue each tick. Needs a cache keyed by ref (a sha never changes, so a
  pinned read is cacheable forever) and conditional requests for moving refs.
- **Offline and the pod.** The pod has no `~/github`; the viewer's published documents are
  already built elsewhere. Pinned fetches would let the pod build them itself, which is the
  point, but needs a read-only token in the pod and a decision on where it lives.
- **Ordering and identity.** Issues number per repo; activities need a stable id. The id
  should be a URL the actor owns (ActivityStreams `id`), not the issue number alone.
- **Local-only repos.** A repo with no remote cannot receive an issue. It stays on the
  `inbox/` transport, which is why that transport is kept.
- **Summit's floor.** Asks to summit's floor use `floor/inbox/<slug>.bib`
  (`nemik-ask`); that is summit's own format and stays summit's, with the Offer mapping
  proposed to summit rather than imposed.

## Steps, smallest first

1. This design, reviewed by mtools:W1710's author and the operator.
2. A pure function from a letter (path, header, body) to an activity and back, with a test
   that round-trips every letter in the fixture fleet. No network.
3. An `Inbox` interface with the file transport behind it, so `nemik-inbound` and
   `nemik-check --letters` read through it and nothing else changes.
4. A read-only GitHub transport for private repos, behind the same interface, off by default.
5. The pinned queue fetch, with the ref cache.
6. Writing (opening an issue), only after 1 to 5 and an explicit go.
