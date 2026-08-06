import os
from pathlib import Path
from devfx.config import Configuration

class ConfigurationLoader:
    def load():
        environment = os.getenv("ENVIRONMENT", None)
        if environment is None:
            raise Exception("ENVIRONMENT variable not set")

        # Get the directory where this file is located (config/)
        config_dir = Path(__file__).parent
        config_file = config_dir / f'config.{environment}.json'
        Configuration.load(str(config_file))
