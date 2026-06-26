# Claude Code Agents — Quick Reference Guide

## What Are Agents?

Agents are reusable specialist subagents you define in YAML. They run in their own context window (keeping your main conversation clean) and have access to only the tools you specify. Think of them as teammates you can delegate specific types of work to.

## File Locations

| Level | Path | Scope |
|-------|------|-------|
| **Project** | `<repo>/.claude/agents/<name>.yaml` | Available only in that repo. Committed to git = shared with team. |
| **Global** | `~/.claude/agents/<name>.yaml` | Available in every project on your machine. Personal only. |

Project agents override global agents if they share the same name.

## YAML Schema

```yaml
---
name: agent-name              # Required. Kebab-case identifier.
description: >                # Required. When/why to use this agent.
  One-line description shown in agent selection.
tools:                        # Required. Allowlist of tools this agent can use.
  - WebSearch
  - WebFetch
  - Read
  - Glob
  - Grep
  - Bash
  - mcp__context7__resolve-library-id    # MCP tools need full qualified name
  - mcp__context7__query-docs
model: sonnet                 # Optional. Default: same as parent. Options: opus, sonnet, haiku
---

System prompt / instructions go here, below the YAML front matter.
This is the agent's "personality" and workflow instructions.
Write it like you're briefing a colleague.
```

## Key Rules

### Tool Names
- **Built-in tools**: Use the exact name — `Read`, `Write`, `Edit`, `Bash`, `Glob`, `Grep`, `WebSearch`, `WebFetch`, etc.
- **MCP tools**: Use the fully qualified name — `mcp__<server>__<tool>`. Example: `mcp__context7__query-docs`, NOT just `context7`.
- An agent can **only** use tools listed in its `tools` array. If a tool isn't listed, the agent can't call it.

### Model Selection
- `opus` — Most capable, slowest, most expensive. Use for complex reasoning tasks.
- `sonnet` — Good balance. Use for most agents (research, code review, exploration).
- `haiku` — Fastest, cheapest. Use for simple/repetitive tasks.
- Omit `model` to inherit the parent's model.

## How Agents Are Invoked

Agents are called via the `Agent` tool in two ways:

1. **By Claude automatically** — If the task matches an agent's description, Claude may delegate to it.
2. **By you explicitly** — Ask Claude to "use the docs-researcher agent to look up X".

The parent agent sends a prompt to the subagent, the subagent works independently, and returns a result. The parent never sees the subagent's intermediate tool calls — only the final output.

## Design Principles

### 1. Single Responsibility
Each agent should do ONE thing well. Don't make a "do everything" agent.

```
Good:  docs-researcher, code-reviewer, test-writer
Bad:   general-helper, smart-agent
```

### 2. Minimal Tool Access
Only give tools the agent actually needs. Fewer tools = less confusion, better focus.

```yaml
# A docs agent doesn't need Edit or Write
tools:
  - WebSearch
  - WebFetch
  - mcp__context7__resolve-library-id
  - mcp__context7__query-docs
```

### 3. Clear Instructions
The system prompt (below front matter) should define:
- **Role** — What the agent is
- **Workflow** — Step-by-step process
- **Output format** — What to return (and what NOT to)
- **Boundaries** — What it should NOT do

### 4. Use Cheaper Models for Simple Tasks
Don't use opus for grep-and-summarize work. Match model to complexity.

## Example Agents

### Documentation Researcher
```yaml
---
name: docs-researcher
description: Research external documentation. Prefer official docs. Return concise summaries.
tools:
  - WebSearch
  - WebFetch
  - mcp__context7__resolve-library-id
  - mcp__context7__query-docs
model: sonnet
---
You are a documentation researcher. Query Context7 first.
Only web search if Context7 is insufficient.
Return: summary, key APIs, examples, caveats, links.
Do not solve the user's task — only research.
```

### Codebase Explorer
```yaml
---
name: codebase-explorer
description: Deep codebase exploration — find patterns, trace flows, map dependencies.
tools:
  - Read
  - Glob
  - Grep
  - Bash
model: sonnet
---
You explore codebases to answer structural questions.
Use Glob/Grep to find files, Read to examine them.
Return a concise summary of what you found with file paths and line numbers.
Do not modify any files.
```

### Test Writer
```yaml
---
name: test-writer
description: Write tests for Python code using pytest.
tools:
  - Read
  - Glob
  - Grep
  - Write
  - Edit
  - Bash
model: sonnet
---
You write pytest tests. Read the source code first to understand behavior.
Follow existing test patterns in the repo.
Run tests with `cd backend && pytest <file>` to verify they pass.
```

## When to Use Agents vs Direct Tools

| Situation | Use |
|-----------|-----|
| Quick file search | Direct `Glob`/`Grep` — no agent needed |
| Read one file | Direct `Read` — no agent needed |
| Deep multi-file exploration | Agent (keeps context clean) |
| External doc research | Agent (isolates web search noise) |
| Parallel independent tasks | Multiple agents in parallel |
| Simple question | Direct answer — no agent needed |

## Referencing Agents in CLAUDE.md

To make Claude automatically use an agent, add instructions to your project's `CLAUDE.md`:

```markdown
## Documentation Policy
When implementation depends on a framework, SDK, library or API,
delegate to the `docs-researcher` agent for lookup.
```

Without this, Claude will use agents opportunistically based on their descriptions, or when you explicitly ask.

## Debugging

- **Agent can't find a tool**: Check the `tools` list uses exact tool names. MCP tools need `mcp__<server>__<tool>` format.
- **Agent doing too much**: Tighten the system prompt boundaries and remove unnecessary tools.
- **Agent too slow**: Switch to a cheaper `model` or reduce scope.
- **Agent not being used**: Add explicit instructions in CLAUDE.md or ask Claude to use it by name.
