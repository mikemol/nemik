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

## A letter is a mention; an ask is a mention with a state

The operator's reading (2026-10-19): a letter is what tagging a person in a Mastodon post is.
It fits. In ActivityPub a tag is a `Note` carrying a `Mention` tag and addressed (`to`/`cc`)
to the tagged actor; it lands in that actor's inbox. A plain letter is exactly that, and the
post's visibility is the egress line: a post to "mentioned people only" reaches the actors
named and nobody else (a letter between the operator's own private repos), while a public
post is disclosure (a letter to a public repo, which needs the releasable mark).

What a mention does not carry is an obligation. An ask does: it becomes a waypoint in the
recipient's queue, someone must claim it, and it ends in an accept, a reject or a resolve.
So the model is two shapes of one act: a plain letter is a `Note` mentioning the recipient;
an ask is the same `Note` plus an `Offer` of a `Ticket`, whose state the sender's waypoint
follows. Citing `<repo>:W<n>` in a letter is like linking a post: it names the thing and
creates no duty by itself.

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
  public repo unless the letter is marked releasable, and say why when it refuses. A repo's
  visibility can change after it was last seen, so the adapter reads it at send time and
  never caches it.
- No credential is written to disk by nemik: the API token comes from the environment the
  operator already provisions, and the YubiKey is never opened.
- Nothing is sent until this design is reviewed and a card says so.

## The queue read

Each repo's queue would be read through one function a tool can call, not opened from a
sibling directory:

    read_queue(repo, ref_or_live, max_age) -> the paths-forward.json document, and how old it is

- **`ref`** is a commit sha: repeatable, cacheable forever, and for audits (history, a fleet
  read that must name the exact state it read).
- **`live`** is the queue as its owner has it now. A queue is edited live and committed
  rarely, so a sha read can be hours behind the queue a blocker watch needs ("is W1480
  done?"). Live needs a publisher: either the owner's queue published on its own channel
  (nemik-serve's documents carry it) or, for a repo on the same machine, a read of its
  working tree. A branch head is not live, because nothing publishes uncommitted edits.
- **Freshness is the caller's to state.** `max_age` is the staleness the consumer accepts: a
  blocker watch and `nemik-inbound` ask for live with a bound of minutes; the history and the
  viewer's documents accept a sha. The answer carries its age, so a consumer can refuse it.
- **Offline.** A tick must not block on the network. When the read cannot be made, the answer
  is the last good read, marked stale with its age; a caller that cannot use a stale answer
  says so. The function never waits on a connection past a stated bound.

The consumers are not only nemik: mtools' own code reads peers' queues the same way today
(the foreign-blocker reader, `--inbound`, `--prune-landed`, the blocker watch, all opening
`<root>/<repo>/.claude/paths-forward.json` by path), and its lint (mtools:W1708) will ratchet
those reads to zero. They are named consumers of `read_queue`, so one interface fits both.
The ledger and the `inbox/` fold are read the same way. This is the harder half: the fleet
read today is cheap because it is local.

## What this leaves unsolved

- **Latency and rate limits.** A directory read is free; an API read is not. The fleet read
  touches every repo's queue each tick. Needs a cache keyed by ref (a sha never changes, so a
  pinned read is cacheable forever) and conditional requests for moving refs.
- **Offline and the pod.** The pod has no `~/github`; the viewer's published documents are
  already built elsewhere. Pinned fetches would let the pod build them itself, which is the
  point, but needs a read-only token in the pod and a decision on where it lives.
- **Ordering and identity.** Issues number per repo; activities need a stable id. The id
  should be a URL the actor owns (ActivityStreams `id`), not the issue number alone.
- **Local-only repos, and the file fallback as a sibling reach.** A repo with no remote
  cannot receive an issue, so it stays on the `inbox/` transport. But delivery to another
  repo's `inbox/` is a write into `../<repo>/inbox`, exactly the reach mtools:W1708's lint
  ratchets to zero. Proposal, for the operator to confirm: nemik's adapter is the ONE named
  place allowed to know sibling paths, a single declared allowlist entry in the lint, so
  exactly one repo knows; a broker for local-only delivery is the alternative, and costs a new
  moving part for a fallback that should shrink as repos gain remotes.
- **Summit's floor.** Asks to summit's floor use `floor/inbox/<slug>.bib`
  (`nemik-ask`); that is summit's own format and stays summit's, with the Offer mapping
  proposed to summit rather than imposed.

## Steps, smallest first

1. This design, reviewed by mtools:W1710's author and the operator.
2. A pure function from a letter (path, header, body) to an activity and back, with a test
   that round-trips every letter in the fixture fleet. No network. The queue round trip uses
   mtools' pinned fixture `hooks/tests/fixtures/queue/alpha`, byte-identical to nemik's W519
   fixture and pinned by git blob hash, so a format change breaks both at once.
3. An `Inbox` interface with the file transport behind it, so `nemik-inbound` and
   `nemik-check --letters` read through it and nothing else changes.
4. A read-only GitHub transport for private repos, behind the same interface, off by default.
5. `read_queue` with the pinned fetch, the ref cache, the live publisher and the offline answer.
6. Writing (opening an issue), only after 1 to 5 and an explicit go.
