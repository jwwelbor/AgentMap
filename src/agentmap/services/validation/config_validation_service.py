# src/agentmap/services/validation/config_validation_service.py
import hashlib
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import ValidationError as PydanticValidationError

from agentmap.models.config_models import ConfigModel
from agentmap.models.validation.validation_models import ValidationResult
from agentmap.services.config.llm_models_config_service import LLMModelsConfigService
from agentmap.services.logging_service import LoggingService


class ConfigValidationService:
    """
    Validator for AgentMap YAML configuration files.

    Validates structure, types, paths, and provider configurations.
    """

    def __init__(
        self,
        logging_service: LoggingService,
        llm_models_config_service: LLMModelsConfigService,
    ):
        """Initialize the config validator."""
        self.logger = logging_service.get_logger("agentmap.config_validation")
        self.llm_models_config = llm_models_config_service

        self.required_env_vars = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "google": "GOOGLE_API_KEY",
        }

    def validate_file(self, config_path: Path) -> ValidationResult:
        """
        Main validation entry point for a config file.

        Args:
            config_path: Path to the YAML config file to validate

        Returns:
            ValidationResult with all validation issues found
        """
        result = ValidationResult(
            file_path=str(config_path), file_type="config", is_valid=True
        )

        # Calculate file hash for caching
        try:
            with open(config_path, "rb") as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
                result.file_hash = file_hash
        except Exception as e:
            result.add_error(f"Cannot read file: {e}")
            return result

        # Check if file exists and is readable
        if not config_path.exists():
            result.add_error(f"Config file does not exist: {config_path}")
            return result

        if not config_path.is_file():
            result.add_error(f"Path is not a file: {config_path}")
            return result

        try:
            # Load YAML content
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f) or {}

            # Run all validation checks
            self._validate_yaml_structure(config_data, result)
            self._validate_schema(config_data, result)

            # Only run detailed validation if no structural errors
            if not result.has_errors:
                self._validate_paths(config_data, result)
                self._validate_llm_configs(config_data, result)
                self._validate_cross_references(config_data, result)

        except yaml.YAMLError as e:
            result.add_error(f"YAML parsing error: {e}")
        except Exception as e:
            result.add_error(f"Unexpected error during validation: {e}")

        return result

    def _validate_yaml_structure(
        self, config_data: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate basic YAML structure and format."""

        if not isinstance(config_data, dict):
            result.add_error(
                "Config file must contain a YAML dictionary at the root level"
            )
            return

        if not config_data:
            result.add_warning("Config file is empty - will use all default values")
            return

        # Info about top-level sections
        sections = list(config_data.keys())
        result.add_info(
            f"Found {len(sections)} configuration section(s): {', '.join(sections)}"
        )

        # Check for common typos in section names
        expected_sections = {
            "paths",
            "llm",
            "memory",
            "prompts",
            "execution",
            "tracing",
        }
        typo_suggestions = {
            "path": "paths",
            "llms": "llm",
            "memories": "memory",
            "prompt": "prompts",
            "exec": "execution",
            "trace": "tracing",
        }

        for section in sections:
            if section in typo_suggestions:
                result.add_warning(
                    f"Possible typo in section name: '{section}'",
                    suggestion=f"Did you mean '{typo_suggestions[section]}'?",
                )

    def _validate_schema(
        self, config_data: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate the config against the Pydantic schema."""

        try:
            # Validate with Pydantic model
            ConfigModel(**config_data)
            result.add_info("Configuration schema validation passed")

        except PydanticValidationError as e:
            for error in e.errors():
                # Extract field path
                field_path = ".".join(str(loc) for loc in error.get("loc", []))
                message = error.get("msg", "Validation error")
                value = error.get("input")

                result.add_error(
                    message=f"Schema validation error: {message}",
                    field=field_path if field_path else None,
                    value=str(value) if value is not None else None,
                )
        except Exception as e:
            result.add_error(f"Unexpected error during schema validation: {e}")

    def _validate_paths(
        self, config_data: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate path configurations and file/directory existence."""

        # Validate CSV path
        csv_path = config_data.get("csv_path")
        if csv_path:
            csv_file = Path(csv_path)
            if not csv_file.exists():
                result.add_warning(
                    f"CSV file does not exist: {csv_path}",
                    field="csv_path",
                    suggestion="Create the file or update the path",
                )
            elif not csv_file.is_file():
                result.add_error(
                    f"CSV path is not a file: {csv_path}", field="csv_path"
                )
            elif not csv_path.endswith(".csv"):
                result.add_warning(
                    f"CSV path does not have .csv extension: {csv_path}",
                    field="csv_path",
                )

        # Validate storage config path
        storage_config_path = config_data.get("storage_config_path")
        if storage_config_path:
            storage_file = Path(storage_config_path)
            if not storage_file.exists():
                result.add_info(
                    f"Storage config file does not exist: {storage_config_path}",
                    field="storage_config_path",
                    suggestion="File will be created when needed",
                )

        # Validate paths section
        paths_config = config_data.get("paths", {})
        if paths_config:
            path_fields = {
                "custom_agents": "Custom agents directory",
                "functions": "Functions directory",
                "compiled_graphs": "Compiled graphs directory",
            }

            for field, description in path_fields.items():
                path_value = paths_config.get(field)
                if path_value:
                    path_obj = Path(path_value)

                    # For directories, check if parent exists (directory might be created later)
                    if not path_obj.exists():
                        if path_obj.parent.exists():
                            result.add_info(
                                f"{description} will be created: {path_value}",
                                field=f"paths.{field}",
                            )
                        else:
                            result.add_warning(
                                f"{description} parent directory does not exist: {path_value}",
                                field=f"paths.{field}",
                                suggestion="Ensure parent directory exists",
                            )
                    elif path_obj.is_file():
                        result.add_error(
                            f"{description} path is a file, not a directory: {path_value}",
                            field=f"paths.{field}",
                        )

        # Validate prompts paths
        prompts_config = config_data.get("prompts", {})
        if prompts_config:
            prompts_dir = prompts_config.get("directory")
            if prompts_dir:
                prompts_path = Path(prompts_dir)
                if not prompts_path.exists():
                    result.add_info(
                        f"Prompts directory will be created: {prompts_dir}",
                        field="prompts.directory",
                    )

            registry_file = prompts_config.get("registry_file")
            if registry_file:
                registry_path = Path(registry_file)
                if not registry_path.exists():
                    result.add_info(
                        f"Prompts registry file will be created: {registry_file}",
                        field="prompts.registry_file",
                    )

    def _validate_llm_configs(
        self, config_data: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate LLM provider configurations."""

        llm_config = config_data.get("llm", {})
        if not llm_config:
            result.add_info(
                "No LLM configuration found - will use environment variables and defaults"
            )
            return

        providers = ["openai", "anthropic", "google"]
        configured_providers = []

        for provider in providers:
            provider_config = llm_config.get(provider, {})
            if provider_config:
                configured_providers.append(provider)
                self._validate_provider_config(provider, provider_config, result)

        if configured_providers:
            result.add_info(
                f"LLM providers configured: {', '.join(configured_providers)}"
            )
        else:
            result.add_info(
                "No LLM providers explicitly configured - will use environment variables"
            )

    def _validate_provider_config(
        self, provider: str, config: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate configuration for a specific LLM provider."""

        field_prefix = f"llm.{provider}"

        # Check API key
        api_key = config.get("api_key", "")
        env_var = self.required_env_vars.get(provider)

        if not api_key and env_var:
            env_value = os.environ.get(env_var)
            if not env_value:
                result.add_warning(
                    f"No API key configured for {provider}",
                    field=f"{field_prefix}.api_key",
                    suggestion=f"Set api_key in config or {env_var} environment variable",
                )
            else:
                result.add_info(
                    f"{provider} API key found in environment variable {env_var}"
                )
        elif api_key:
            # Basic API key format validation
            if len(api_key) < 10:
                result.add_warning(
                    f"{provider} API key seems too short",
                    field=f"{field_prefix}.api_key",
                    suggestion="Verify the API key is complete",
                )

            # Check for placeholder values
            placeholder_patterns = ["your_api_key", "api_key_here", "replace_me", "xxx"]
            if any(pattern in api_key.lower() for pattern in placeholder_patterns):
                result.add_error(
                    f"{provider} API key appears to be a placeholder",
                    field=f"{field_prefix}.api_key",
                    value=api_key,
                    suggestion="Replace with your actual API key",
                )

        # Validate model name
        model = config.get("model")
        if model:
            known_models = self.llm_models_config.get_known_models(provider)

            if known_models and model not in known_models:
                result.add_info(
                    f"Using non-standard model for {provider}: {model}",
                    field=f"{field_prefix}.model",
                    suggestion=f"Common models: {', '.join(known_models)}",
                )

        # Validate temperature
        temperature = config.get("temperature")
        if temperature is not None:
            try:
                temp_float = float(temperature)
                if temp_float < 0 or temp_float > 2:
                    result.add_warning(
                        f"{provider} temperature {temp_float} is outside typical range 0-2",
                        field=f"{field_prefix}.temperature",
                    )
            except (ValueError, TypeError):
                result.add_error(
                    f"{provider} temperature must be a number",
                    field=f"{field_prefix}.temperature",
                    value=str(temperature),
                )

    def _validate_cross_references(
        self, config_data: Dict[str, Any], result: ValidationResult
    ) -> None:
        """Validate cross-references between different config sections."""

        # Check if tracing is enabled but required fields are missing
        tracing_config = config_data.get("tracing", {})
        if tracing_config.get("enabled"):
            mode = tracing_config.get("mode", "langsmith")

            if mode == "langsmith":
                api_key = tracing_config.get("langsmith_api_key")
                env_key = os.environ.get("LANGCHAIN_API_KEY")

                if not api_key and not env_key:
                    result.add_warning(
                        "Tracing enabled with LangSmith mode but no API key found",
                        field="tracing.langsmith_api_key",
                        suggestion="Set langsmith_api_key or LANGCHAIN_API_KEY environment variable",
                    )

                project = tracing_config.get("project")
                if not project or project == "your_project_name":
                    result.add_warning(
                        "Tracing enabled but project name not configured",
                        field="tracing.project",
                        suggestion="Set a meaningful project name for tracing",
                    )

            elif mode == "local":
                local_dir = tracing_config.get("local_directory", "./traces")
                local_path = Path(local_dir)

                if not local_path.parent.exists():
                    result.add_warning(
                        f"Local tracing directory parent does not exist: {local_dir}",
                        field="tracing.local_directory",
                    )

        # Check execution policy configuration
        execution_config = config_data.get("execution", {})
        if execution_config:
            success_policy = execution_config.get("success_policy", {})
            if success_policy:
                policy_type = success_policy.get("type", "all_nodes")

                if policy_type == "critical_nodes":
                    critical_nodes = success_policy.get("critical_nodes", [])
                    if not critical_nodes:
                        result.add_warning(
                            "Success policy set to 'critical_nodes' but no critical nodes specified",
                            field="execution.success_policy.critical_nodes",
                            suggestion="Add node names to critical_nodes list",
                        )

                elif policy_type == "custom":
                    custom_function = success_policy.get("custom_function")
                    if not custom_function:
                        result.add_error(
                            "Success policy set to 'custom' but no custom_function specified",
                            field="execution.success_policy.custom_function",
                        )
