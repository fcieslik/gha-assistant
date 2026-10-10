# Orchestration contract

This directory contains the repository-local contract used by the Coding Workflow Orchestrator.

The delivery.default setting selects the handoff after a successful Workflow run: local fast-forwards the saved target branch, pr prepares a GitHub Pull Request, and none leaves the Feature branch untouched. An invocation-level --delivery overrides the default for a new run.

- `.orchestrator/config.yaml` is shared project policy. It selects the Worker role, Agent profile, downstream engineering skill, timeout, and attempt budget.
- `.orchestrator/runs/` contains ephemeral Workflow state and is intentionally ignored by Git.
- `workflow.validation` in `.orchestrator/config.yaml` defines the validation commands as free-form `name: command` entries (at least one) plus one `timeoutSeconds` applied independently to each command. `flow` runs them sequentially in file order after every Ticket and again in the final Feature worktree. The default commands assume a pnpm project; adapt them to this repository before validating a completed Workflow run.
- Agent profiles select the native Worker executable with `kind: codex`, `kind: claude-code`, or `kind: pi`. Optional `provider` and `model` values are one-launch overrides; when omitted, the selected Agent uses its native configuration. For example, Pi may be configured as:

  ```yaml
  agents:
    pi-openai:
      kind: pi
      provider: openai
      model: gpt-5.6-luna
  ```

- `workflow.securityScan` is an optional shell command. When set, the Orchestrator runs it once in the Feature worktree after the Ticket queue completes, reads the report, and asks before delivery if it shows findings or an incomplete scan. `flow` does not run it.
- Workers may write only their assigned Feature worktree and their preallocated result output directory. They must not modify Workflow state or the execution record.

The version 1 default Worker uses the Codex Agent profile and the `implement` skill. Timeout values are limited to 60–7,200 seconds and the attempt budget is bounded. Agent process arguments are deliberately not configurable in version 1.
