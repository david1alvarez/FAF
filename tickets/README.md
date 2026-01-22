# Tickets

This directory contains work tickets for Claude Code (or other AI coding agents) to implement.

## Ticket Format Specification

Each ticket is a standalone markdown file that must contain **all context necessary** for an AI agent to complete the work. Assume the agent has:
- Access to the full codebase
- No memory of previous conversations
- Limited context window (~100-200k tokens)

### Required Sections

Every ticket **must** include these sections in order:

```markdown
# TICKET-XXX: [Title]

## Status
[NOT STARTED | IN PROGRESS | BLOCKED | COMPLETE]

## Priority
[P0-Critical | P1-High | P2-Medium | P3-Low]

## Description
[2-4 sentences max. What needs to be done and why.]

## Acceptance Criteria
[Bulleted list. Each item must be independently verifiable.]

## Technical Context
[Key files, dependencies, architectural decisions the agent needs to know.
Include links to external docs/specs if needed.]

## Out of Scope
[Explicit list of what this ticket does NOT cover. Prevents scope creep.]

## Testing Requirements
[How to verify the work is complete. Commands to run, expected outputs.]

## References
[Links to relevant docs, prior tickets, or external resources.]
```

### Optional Sections

Include only if relevant:

```markdown
## Dependencies
[Other tickets that must be completed first]

## Security Considerations
[If the work touches auth, secrets, user data, etc.]

## Performance Considerations
[If the work has performance implications]

## Future Work
[Known follow-up tickets this will enable]
```

## Naming Convention

Tickets are numbered sequentially with zero-padding:
- `001-short-descriptive-name.md`
- `002-another-ticket.md`

Use lowercase, hyphens for spaces, no special characters.

## Workflow

1. Human creates ticket with full context
2. AI agent reads ticket + relevant code
3. AI agent implements, commits with message referencing ticket
4. Human reviews PR
5. On merge, update ticket status to COMPLETE

## Principles

- **Self-contained**: Agent should never need to ask clarifying questions
- **Minimal**: Include only what's needed, nothing more
- **Verifiable**: Every acceptance criterion must be testable
- **Atomic**: One logical unit of work per ticket