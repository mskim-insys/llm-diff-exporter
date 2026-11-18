# AI Coding Workspace Setup (Empty Workspace)

Nov 9, 2026 · @유저

## 1. Principles

This guide sets up the Markdown files that carry project context across AI coding sessions, starting from an empty workspace. Commit messages record what changed; these files record what is required now, why a choice was made, and which alternatives were rejected.

Documents fragment when nobody knows where the current truth of a fact lives. Three defaults help prevent that. Break them when you have a good reason:

1. **One home per fact.** A requirement, a status, a rationale, or a usage instruction lives in one main document. Other documents should link to it; a short summary beside the link is fine.
2. **Link, don't copy.** Refer to code, tests, and other documents by path instead of restating them.
3. **Create lazily.** Create a file when its trigger (section 3) is met, or earlier when you already know it will be needed. Avoid empty templates with nothing in them.

## 2. Day-zero setup

An empty workspace needs only two files to start. Add the others when a trigger fires, or earlier when you know they will be needed.

```text
AGENTS.md      # navigation for agents: where to start, commands, boundaries
README.md      # current usage and behavior
```

As the project grows, the layout grows in this order:

```text
DECISIONS.md          # first real decision or rejected approach
specs/<topic>.md      # a requirement too big to state in a few lines
worklogs/<topic>.md   # work that spans more than one session
archive/              # superseded specs and finished worklogs
```

Defaults that fit most projects (adapt them when yours differs):

- **Nearest `AGENTS.md` wins.** If the workspace is a subfolder of a larger repo, keep the real context in the subfolder's `AGENTS.md`. A root `AGENTS.md` only points to it.
- **Nested workspaces.** A workspace may contain another one, such as a fork cloned into a subfolder with its own `AGENTS.md` and docs. Each keeps its own docs, and the outer one links to the inner by path. The outer workspace may plan work that the inner one carries out: put a Handoff section in the outer spec and let the inner workspace own execution status.
- **Pair by name.** `specs/auth.md` and `worklogs/auth.md` share a slug.
- **Avoid extra index files.** `AGENTS.md` lists the active specs by default; add an index file once that list gets long.
- **Tool-specific files** (for example `CLAUDE.md`) are one-line pointers to `AGENTS.md`.
- **Track the docs in version control** so a fresh clone starts with the same context.

## 3. Responsibilities and creation triggers

Each document answers one question and must not hold another's content.

| Document | Answers | Must not contain | Create when |
| --- | --- | --- | --- |
| `README.md` | How do I use this, and how does it behave now? | History, rationale, progress | Day zero |
| `AGENTS.md` | Where do I start, how do I build and test, what must I not touch? | Rules copied from other docs | Day zero; keep it short, roughly 100 lines at most |
| `DECISIONS.md` | Why X over Y, and what constraints follow? | Routine progress | A tried approach was discarded, a choice was made among viable options, an environment quirk must be known, or an improvement was deliberately deferred |
| `specs/<topic>.md` | What must be true? Requirements, constraints, acceptance criteria | Progress, rationale for choosing | The requirement is non-trivial or spans sessions |
| `worklogs/<topic>.md` | What changed, how was it verified, what is next? | Requirements, re-explained implementation | Work spans more than one session |
| `archive/` | Finished worklogs and superseded specs | Anything active | A spec is superseded or a topic is done |

Trivial changes such as typo fixes and formatting usually need no entry.

**Ownership of next steps.** The spec owns requirements, including unmet acceptance criteria. The worklog owns status and the handover. Avoid listing the same open item in both; if it appears in both, the worklog links to the spec criterion.

**Plans.** A complex plan usually lives as a section inside the spec; split it into its own file if it grows too long. For large work split across sessions, add a Milestones section to the spec: each milestone (M1, M2, ...) lists its exit criteria, and completion is recorded only by checking those criteria. The worklog should not keep its own milestone status table, and a file per milestone or a separate handover file is rarely needed.

**Milestone rules.** Milestone work usually gets a worklog. A milestone counts as done once its spec criteria are checked and the `Verified` line shows how. Tag each session entry with its milestone. A scope change updates the spec first, then gets a short worklog note.

## 4. Templates

Delete any section that has nothing to say.

**AGENTS.md** (navigation only)

```markdown
# <Project name>

<One or two sentences: what this is and who uses it.>

## Read first
- README.md for current usage and behavior
- Active specs: specs/<topic>.md (list only active ones)
- DECISIONS.md before changing architecture or retrying a past approach

## Commands
- Build: `<command>`
- Test: `<command>`

## Boundaries
- Do not edit: <generated files, vendored code, secrets>
- Ask first: <risky or irreversible actions>

## Workspace docs
- Rules for these files: <path to this guide>
```

**README.md** (current state only)

```markdown
# <Project name>
<What it does, in one paragraph.>

## Usage
## Build and run
## Current behavior and limits
```

**specs/\<topic>.md**

```markdown
# Spec: <topic>
Status: draft | active | superseded by <link>
Last updated: YYYY-MM-DD

## Goal
## Requirements
## Constraints
## Acceptance criteria
- [ ] <criterion>
## Milestones (only for large work split across sessions)
### M1 <name>
- Exit criteria: <the acceptance criteria above that must be checked>
### M2 <name>
- Exit criteria: <...>
## Plan (only for complex work)
```

**worklogs/\<topic>.md**

```markdown
# Worklog: <topic>
Spec: specs/<topic>.md
Status: in progress | done

## Handover (overwrite each session)
- Current milestone: <M2, criteria live in the spec>
- Done and verified: <what, with the check that proved it>
- Not done / partial: <what, and why>
- First step next session: <one concrete action>
- Read first: <file paths>
- Traps: <gotchas, environment quirks, links to DECISIONS entries>
- Open questions: <blockers that need the user>

## Sessions (newest first)
### YYYY-MM-DD · <milestone, if any>
- Changed: <what, with links to files>
- Verified: <command or check, and the result>
- Risks / open: <link to the spec criterion, do not restate it>
```

**DECISIONS.md entry**

```markdown
## YYYY-MM-DD-NN Short title
- Context: why this decision was needed
- Decision: what was decided
- Alternatives considered and rejected: what was tried and why it was dropped (include evidence or numbers)
- Impact / follow-ups: constraints this creates, or conditions for revisiting it
```

**Entry ID rule.** The ID is a date plus a two-digit sequence number `NN`. Agents cannot see the current time: use the date from context and avoid running a terminal command just to get a timestamp. If the last entry has the same date, use its `NN` plus 1; otherwise start at `01`. Avoid reusing or renumbering an ID, because other documents may link to it.

## 5. Session protocol

Read only what the task needs at the start, and reconcile the documents before stopping.

**Start of a session**

1. Read the nearest `AGENTS.md`.
2. Read the spec and worklog for the topic you will touch, starting with the worklog's Handover block.
3. Scan `DECISIONS.md` titles before changing architecture or retrying an approach; open full entries only for matches.
4. Read `README.md` only if you need current behavior. Skip `archive/` unless a document points there.

**End of a session**

- [ ] A requirement changed: update the spec and its `Last updated` date.
- [ ] The work spans sessions: add a worklog entry tagged with its milestone and overwrite the Handover block. The handover is expected for milestone work and optional for small tasks.
- [ ] A discarded approach, choice between options, environment quirk, or deferred improvement came up: append a `DECISIONS.md` entry.
- [ ] User-visible behavior changed: update `README.md` with current behavior only.
- [ ] A fact now appears in two places: keep the copy in its home and replace the other with a link.
- [ ] A topic is finished or a spec is superseded: move it to `archive/` and name the replacement.

## 6. Bootstrap prompt

Paste this into the first session of a new workspace. Keep this guide where agents can read it, for example in global agent instructions or as a file in the repo, and point to it from the prompt and from `AGENTS.md`.

```text
Set up documentation for this empty workspace following the "AI Coding Workspace Setup (Empty Workspace)" guide.

1. Ask me for: the project name, a one or two sentence description, the build and test commands (if known), and anything agents must not touch.
2. Create AGENTS.md (keep it short) and README.md from the templates. Add other files only if I ask or the project clearly needs them.
3. If the workspace is a subfolder of a larger repository, put the real context in this folder's AGENTS.md and tell me whether a root AGENTS.md should point here.
4. Check whether these docs will be version-controlled and report the result.

From now on, follow the session start and end protocol. Create DECISIONS.md, specs/, worklogs/, and archive/ when their creation triggers fire, or earlier when I ask.
```
