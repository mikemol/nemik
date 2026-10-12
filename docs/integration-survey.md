# nemik integration survey: PM tools (2026-10-12)

Context: nemik reads `.claude/paths-forward.json` queues, never writes them; emits a graph,
critical path (step-counted, no durations), and `nemik-ics` for dated cards (docs/positioning.md).
So the natural direction is **export out of nemik** (read-only mirror), with import only as residue.

**Verification note.** Docs URLs below are the vendors' own doc pages, cited from prior knowledge;
they were NOT fetched live in this session. Every claim is therefore at best "cited, not re-read".
Claims I hold with lower confidence are marked **UNVERIFIED** explicitly. Treat this file as a map
to check, not as a checked map (read-your-writes: confirm against the URL before building).

## 1. GanttProject (desktop, Java, GPL)
- Formats: native `.gan` (XML); imports/exports MS Project XML (MSPDI) and MPX; CSV import/export;
  export PDF/PNG/HTML. https://www.ganttproject.biz/ , https://help.ganttproject.biz/ (import/export pages)
- API: none (desktop app; no REST). UNVERIFIED that no headless CLI exists beyond `-export` options
  (a command-line export mode is documented in the help wiki per memory).
- Plugins: Eclipse-RCP-style OSGi plugin bundles in Java (exporters/importers are themselves plugins
  in the source tree, https://github.com/bardsoftware/ganttproject). No public plugin marketplace;
  distribution = ship a jar into the plugins dir. UNVERIFIED that this is a supported third-party path.

## 2. ProjectLibre (desktop, Java, CPAL)
- Formats: native `.pod`; reads/writes MS Project `.mpp` (read) and MSPDI `.xml`; reads `.gan`
  via MPXJ. https://www.projectlibre.com/ (product page, "compatible with Microsoft Project").
  UNVERIFIED exact read/write matrix; it is built on MPXJ (https://www.mpxj.org/), whose format list
  is the reliable bound.
- API: desktop has none. ProjectLibre Cloud (SaaS) API: UNVERIFIED.
- Plugins: none documented. UNVERIFIED.

## 3. OpenProject (web, Ruby on Rails, GPLv3)
- Formats: work-package export CSV, XLS, PDF, Atom; import of MS Project via MSPDI XML / Jira /
  CSV importers (newer releases). https://www.openproject.org/docs/user-guide/work-packages/exporting/
  Import tooling: UNVERIFIED which importers are built-in vs enterprise.
- API: REST API v3, HAL+JSON, with a full Relations resource (precedes/follows/blocks/relates).
  https://www.openproject.org/docs/api/ ; auth: API key (basic), OAuth2 apps, session.
  https://www.openproject.org/docs/api/introduction/ . Webhooks: configurable outgoing webhooks for
  work packages/projects. https://www.openproject.org/docs/system-admin-guide/api-and-webhooks/
- Plugins: Rails engines (Ruby gems) loaded via Gemfile.plugins; can add models, API endpoints, views,
  hooks. https://www.openproject.org/docs/development/create-openproject-plugin/ Distribution = gem /
  git source; requires self-hosting, not available on OpenProject cloud.

## 4. Jira Cloud
- Formats: CSV import (External System Import); export CSV/XML/Word from issue search.
  https://support.atlassian.com/jira-cloud-administration/docs/import-data-from-a-csv-file/
  No MSPDI natively (marketplace apps do it).
- API: REST v3 (+ Agile REST), issue links typed (e.g. "Blocks"). https://developer.atlassian.com/cloud/jira/platform/rest/v3/
  Webhooks (admin or app-registered). https://developer.atlassian.com/cloud/jira/platform/webhooks/
  Auth: API token + basic, OAuth 2.0 (3LO), Forge/Connect app auth.
  https://developer.atlassian.com/cloud/jira/platform/security-overview/
  GraphQL via Atlassian platform gateway (UNVERIFIED for full Jira coverage).
- Plugins: Forge (JS/TS functions on Atlassian infra; UI modules, triggers, custom fields);
  Connect being retired in favour of Forge. https://developer.atlassian.com/platform/forge/
  Distribution: Atlassian Marketplace or private install via `forge install`.
  OSLC: no native OSLC CM provider (third-party adapters exist). UNVERIFIED.

## 5. GitHub Issues / Projects
- Formats: no issue import format; Projects export view to CSV (UNVERIFIED, recalled as a Projects
  "export" menu item). Issue migration is via API/ GitHub Enterprise Importer (repos, not loose CSV).
- API: REST https://docs.github.com/en/rest/issues ; GraphQL (Projects v2 is GraphQL-only)
  https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects
  Issue dependencies ("blocked by"/"blocking") and sub-issues have REST endpoints (2025);
  https://docs.github.com/en/rest/issues/issue-dependencies (UNVERIFIED path).
  Webhooks: repo/org webhooks incl. `issues`, `projects_v2_item`. https://docs.github.com/en/webhooks
  Auth: PAT (fine-grained), GitHub App, OAuth App. https://docs.github.com/en/apps
- Plugins: no in-product plugin model. Extension = GitHub Apps (external services), Actions
  (workflows in repo), CLI extensions. https://docs.github.com/en/actions

## 6. Forgejo
- Formats: none for issues beyond repo migration (migrates issues from GitHub/Gitea/GitLab via API).
  https://forgejo.org/docs/latest/user/ (migration). No CSV/MSPDI.
- API: Gitea-compatible REST v1 with Swagger at `/api/swagger`; issue dependencies endpoints exist
  (`/repos/{o}/{r}/issues/{i}/dependencies`, `/blocks`). https://forgejo.org/docs/latest/user/api-usage/
  (dependency endpoints UNVERIFIED by page, known from Gitea swagger). Webhooks: Forgejo/Gitea/Slack
  etc. per repo/org. https://forgejo.org/docs/latest/user/webhooks/ Auth: access tokens (scoped),
  OAuth2 provider, basic. Forgejo also ships Forgejo Actions (CI).
- Plugins: none (no plugin system; customization = templates/themes, Actions, external services).
  https://forgejo.org/docs/latest/admin/customization/ (UNVERIFIED that docs state "no plugins" plainly).
  Note: nemik already ships via Forgejo (push-is-deploy), so a token & host already exist.

## 7. MS Project desktop
- Formats: `.mpp` (binary, proprietary), MSPDI XML (`.xml`, documented schema), `.mpt`, CSV/XLSX via
  import/export wizard. MSPDI schema: https://learn.microsoft.com/en-us/office-project/xml-data-interchange/introduction-to-project-xml-data
- API: VBA / COM object model (Windows only). https://learn.microsoft.com/en-us/office/vba/api/overview/project
  No REST (desktop). Webhooks: none.
- Plugins: COM/VSTO add-ins (C#/VB.NET), VBA macros; Office Web Add-ins (JS) for Project.
  https://learn.microsoft.com/en-us/office/dev/add-ins/project/project-add-ins
  Distribution: installers, AppSource, centralized deployment.

## 8. Project Online / Planner
- Project Online: CSOM + REST ProjectData (OData reporting) and ProjectServer REST.
  https://learn.microsoft.com/en-us/previous-versions/office/project-javascript-api/ ;
  https://learn.microsoft.com/en-us/office/client-developer/project/project-online-programming-overview
  (UNVERIFIED URL). Project Online is announced for retirement (Sep 2026) in favour of Planner
  (UNVERIFIED date; re-check). Auth: Entra ID (Azure AD) OAuth.
- Planner: Microsoft Graph REST `/planner/tasks` (basic plans; no dependencies in Graph basic tasks).
  https://learn.microsoft.com/en-us/graph/api/resources/planner-overview
  Premium plans (ex-Project for the web) live in Dataverse; API = Dataverse Web API / Schedule API.
  https://learn.microsoft.com/en-us/dynamics365/project-operations/project-management/schedule-api-preview
  (UNVERIFIED applicability to Planner premium). Webhooks: Graph change notifications do NOT cover
  Planner tasks (UNVERIFIED); Dataverse has webhooks/plugins. Auth: Entra ID OAuth2, app permissions.
- Plugins: Dataverse plug-ins (C# .NET, registered on Dataverse events) for premium; Teams/Office
  add-ins. https://learn.microsoft.com/en-us/power-apps/developer/data-platform/plug-ins
  Basic Planner: no plugin model.

## Ranking: cheapest entry for nemik (1 = cheapest)

nemik is read-only over queues and dependency-first, so a one-way export is always the floor.

| tool | order | reasoning |
|---|---|---|
| GanttProject | a > c > b | `.gan`/MSPDI export is one file writer; no API exists. |
| ProjectLibre | a > (b,c absent) | MSPDI export covers it via MPXJ-compatible XML; nothing else to hook. |
| OpenProject | b > a > c | REST v3 has typed relations (blocks/precedes) mapping `blocked_on` 1:1; plugin needs self-host Rails. |
| Jira Cloud | b > a > c | REST issue links carry dependencies; CSV import loses links; Forge is a separate app lifecycle. |
| GitHub | b > c > a | GraphQL/REST with issue dependencies + sub-issues = umbrella; no file import exists. |
| Forgejo | b > (a,c absent) | already-deployed host and token; Gitea-style dependency endpoints map edges directly. |
| MS Project desktop | a > c > b | MSPDI XML is a public schema with PredecessorLink; COM is Windows-only. |
| Project Online/Planner | a > b > c | MSPDI via desktop import is cheapest; Graph Planner lacks dependencies, Online is retiring. |

Common structure under the either/or: every "a" and "b" is the same morphism, card graph ->
(task, predecessor-link) — MSPDI `PredecessorLink`, OpenProject `relation`, Jira `issueLink`,
GitHub/Forgejo `dependency`. Build that projection once; serializers/connectors are thin sinks.
Residue: durations/dates (nemik has none on purpose) must be emitted as 1-step placeholders or omitted,
and any write-back path conflicts with "nemik never writes a queue" — keep import as residue, not goal.

## Candidate cards
- C1: `nemik-export --mspdi` writes the fleet (or one cone) as MSPDI XML with PredecessorLink per `blocked_on`, opening in MS Project, ProjectLibre and GanttProject.
- C2: Define the tool-neutral projection (card -> task, edge -> predecessor, umbrella -> summary) once, with a decode-back test so every sink is checked against it.
- C3: `nemik-export --gan` only if C1's MSPDI round-trip through GanttProject proves lossy.
- C4: A one-way Forgejo mirror connector: each card -> issue, `blocked_on` -> issue dependency, idempotent by card id label.
- C5: Same connector shape for GitHub (GraphQL Projects v2 + sub-issues for umbrellas), reusing C4's projection.
- C6: OpenProject REST v3 mirror via `relations` (blocks/follows), gated on someone actually running OpenProject.
- C7: Jira Cloud mirror via REST issue links, deferred; record as residue unless an operator asks.
- C8: Verification pass: fetch each URL in this survey and clear or confirm every UNVERIFIED mark before any of C1-C7 starts.
