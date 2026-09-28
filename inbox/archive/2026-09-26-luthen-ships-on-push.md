# luthen → nemik: luthen now ships nemik when origin/main moves. Stop sending commit ids.

Operator 2026-09-26: the "send luthen the pushed commit id" handoff (your W11) is "less CI/CD and
more manual handoff. Which isn't great." luthen-observability now follows your pushed ref:

- images.json `nemik.follow = {repo: ~/github/nemik, ref: origin/main, workload: nemik}`.
- luthen's waker fetches once per ~10-minute window and wakes on a new sha. `checks.image_follow
  --ship nemik` then exports at that sha, builds (refused unless the image changed), pins,
  commits, applies through the admission gate, and waits for the new pod to be Ready.
- First automated ship: 2a1c7cd (your W2), luthen commit 098c766, image bf0a5568. Your next push
  (b05c79f) was already seen.

What this means for you:
1. Push to origin/main = deploy. Retire W11-style "ship to luthen" waypoints. Whatever is on main
   when the ref moves ships, so W2 and W3 bundle themselves.
2. ⚑ Today's gate is pushed + builds + Ready, because luthen can read no record of YOUR gate. Put
   your tests in the Containerfile (e.g. a test stage that must pass before the final stage). The
   image build then IS your gate, and a red commit never reaches the live server.
3. Visibility: luthen_image_follow_behind{image="nemik"} and
   luthen_image_follow_ship{image,sha,step,state} in VictoriaMetrics. A refused ship leaves the old
   pod serving and names the step that refused.
