from pathlib import Path
from unittest.mock import Mock

from agentmap.di.container_parts.llm import LLMContainer
from agentmap.services.llm_attempt_file_logger import LLMAttemptFileLogger


def test_di_omits_file_logger_when_disabled():
    config = Mock()
    config.get_llm_call_log_config.return_value = {"enabled": False}

    assert LLMContainer._create_attempt_file_logger(config, Mock()) is None


def test_di_creates_file_logger_from_enabled_configuration(tmp_path):
    config = Mock()
    config.get_llm_call_log_config.return_value = {
        "enabled": True,
        "directory": str(tmp_path),
    }

    logger = LLMContainer._create_attempt_file_logger(config, Mock())

    assert isinstance(logger, LLMAttemptFileLogger)
    assert logger._directory == Path(tmp_path)
