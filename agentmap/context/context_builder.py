import logging
import os


def build_context(config: dict = None) -> dict:
    return {
        "logger": logging.getLogger("AgentMap"),
        "env": config.get("env", "dev") if config else os.getenv("AGENTMAP_ENV", "dev"),
    }
