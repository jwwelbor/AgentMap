# agentmap/logging.py
import logging
import os

# Define custom log levels
TRACE = 5  # Lower than DEBUG (10)

# Register the TRACE level if not already done
if not hasattr(logging, 'TRACE'):
    logging.TRACE = TRACE
    logging.addLevelName(TRACE, "TRACE")

# Add a trace method to the logger class if not already added
if not hasattr(logging.Logger, 'trace'):
    def trace(self, message, *args, **kwargs):
        if self.isEnabledFor(TRACE):
            self._log(TRACE, message, args, **kwargs)
    logging.Logger.trace = trace

def get_logger(name="AgentMap"):
    # Import config here to avoid circular imports
    from agentmap.config import load_config
    
    # Get logger
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        try:
            # Try to load config, but handle case where config system isn't ready
            config = load_config()
            config_log_level = config.get("log_level")
        except Exception:
            # If config loading fails, fall back to environment or default
            config_log_level = None
        
        # Get log level with precedence: env var > config > default
        env_log_level = os.environ.get("AGENTMAP_LOG_LEVEL")
        log_level_name = (env_log_level or config_log_level or "INFO").upper()
        
        # Convert string level to numeric level
        try:
            # Handle both standard levels and our custom TRACE level
            if log_level_name == "TRACE":
                log_level = TRACE
            else:
                log_level = getattr(logging, log_level_name)
        except AttributeError:
            # If log_level_name is invalid, use INFO as fallback
            log_level = logging.INFO
            print(f"Warning: Invalid log level '{log_level_name}', using INFO")
        
        # Add handler with formatter
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Set level from config
        logger.setLevel(log_level)
        
    return logger