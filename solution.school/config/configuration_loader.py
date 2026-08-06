from pathlib import Path
from devfx.config import Configuration
from .environment import Environment

class ConfigurationLoader:
    def load():
        # environment.json is the single source of truth. Nothing here consults an
        # environment variable: two sources would mean no way to tell, from the
        # outside, which one answered.
        environment = Environment.get()

        # Get the directory where this file is located (config/)
        config_dir = Path(__file__).parent
        config_file = config_dir / f'config.{environment}.json'
        Configuration.load(str(config_file))
