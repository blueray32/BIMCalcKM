import logging
import structlog
from bimcalc.core.logging import configure_logging

def verify_logging():
    configure_logging()
    logger = structlog.get_logger()
    logger.info("verification_log", status="success", message="Logging to file works!")
    
    print("Log message sent.")

if __name__ == "__main__":
    verify_logging()
