import logging
from lib.utils import load_yml, auth
import docker

# Define log level and format
LOG_LEVEL = 'info'
logging.basicConfig(
    level=logging.getLevelName(LOG_LEVEL.upper()),
    format='%(asctime)s | %(levelname)s | %(name)s | %(lineno)s | %(thread)s | %(funcName)s | %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S%z'
)

# Load configuration
config = load_yml("items.yml")

target_auth = auth()

# Create docker client
docker_client = docker.APIClient(timeout=60, base_url='unix:///var/run/docker.sock')
