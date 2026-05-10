# tepilora-mcp-python - public release mirror

Public release mirror of `Admintepilora/TepiloraMCP`.

This repository is automatically synced from the private source via the
`Export Public MCP` workflow on tag push (`v*` / `test-v*`).

**Do not push directly here.** All package source changes flow from the private
source repository.

## Releases

- `v*` -> PyPI
- `test-v*` -> TestPyPI

Both release paths are gated by `gate-ci-status`: CI must be green on the
target SHA before publishing.
