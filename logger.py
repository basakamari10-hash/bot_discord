import sys
import logging

def setup_logger() -> logging.Logger:
    logger = logging.getLogger("IslamicAI")
    logger.setLevel(logging.INFO)
    
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger

LOGGER = setup_logger()
