## 🧱 Scaffold System Migration

| Legacy Component | Proposed New Location     | Notes |
|------------------|---------------------------|-------|
| `scaffold.py`    | `GraphScaffoldService`    | Service handles graph/agent/function scaffolds |
| Templates        | `templates/` or embedded  | Store .tpl/.txt scaffold templates here |
| CLI support      | `cli/commands/scaffold.py`| Add argparse or Typer CLI commands |

---
class GraphScaffoldService:
    def scaffold_graph_csv(self, name: str) -> Path:
        """Create a starter CSV for a new graph."""
        ...

    def scaffold_agent_class(self, name: str) -> Path:
        """Create a starter agent class in user-defined directory."""
        ...

    def scaffold_edge_function(self, name: str) -> Path:
        """Scaffold a Python function for dynamic edge routing."""
        ...

### Suggested Service Methods

- `scaffold_graph_csv(name: str) -> Path`
- `scaffold_agent_class(name: str) -> Path`
- `scaffold_edge_function(name: str) -> Path`
