import logging

# Define custom TRACE level (lower than DEBUG)
TRACE = 5  # Lower number = more verbose
logging.addLevelName(TRACE, "TRACE")

# Add a trace method to the logger class
def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

# Add the method to the Logger class
logging.Logger.trace = trace


def get_logger(name="AgentMap"):
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(TRACE)
    return logger
