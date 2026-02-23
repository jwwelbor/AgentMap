# AgentMap — Project Rules

## Configuration Change Checklist

When modifying `src/agentmap/services/config/app_config_service.py` or adding
new `get_*_config()` / `get_value()` accessors for config keys:

1. **Update the template** — add the new section/keys to
   `src/agentmap/templates/config/agentmap_config.yaml.template`
2. **Update the root config** — keep `agentmap_config.yaml` in sync with the template
3. **Update template tests** — add assertions in
   `tests/fresh_suite/unit/services/config/test_config_template_completeness.py`
4. **Update docs** — add/revise the relevant page under
   `docs-docusaurus/docs/reference/services/`
