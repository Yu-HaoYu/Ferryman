import logging
from utils import load_yml, create_dir
from typing import Dict, List

# Define log level and format
LOG_LEVEL = 'info'
logging.basicConfig(
    level=logging.getLevelName(LOG_LEVEL.upper()),
    format='%(asctime)s | %(levelname)s | %(name)s | %(lineno)s | %(thread)s | %(funcName)s | %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)

create_dir("history")

# Load configuration
config = load_yml("items.yml")

