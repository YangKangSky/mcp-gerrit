import os
import logging

# Set log directory to project root/logs
LOG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../logs'))
os.makedirs(LOG_DIR, exist_ok=True)  # Ensure the logs directory exists

LOG_FILE = os.path.join(LOG_DIR, "mcp_server.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"Logging to file: {LOG_FILE}")