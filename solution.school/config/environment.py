import json
from pathlib import Path

"""------------------------------------------------------------------------------------------------
"""
CONFIG_DIRECTORY = Path(__file__).resolve().parent
ENVIRONMENT_FILE = CONFIG_DIRECTORY / 'environment.json'

"""------------------------------------------------------------------------------------------------
The single source of truth for which environment this is.

It is a *file* rather than an environment variable so that one answer serves
every process -- the server, the generator, the exporter, the tests -- without
each launcher, task and terminal profile having to declare it. Eleven places
used to say it; this says it once.

Deliberately, nothing here reads `ENVIRONMENT`. A variable that silently
overrode the file would recreate exactly the ambiguity the file exists to
remove: two sources of truth, and no way to tell from the outside which one
answered.

Nothing writes it either. `environment.json` is edited -- by hand, or by
whatever deploys the application -- and every entry point only reads. That is
what keeps a deployment safe: an image built for `prod` is never rewritten by
the thing it is running.
"""
class Environment:
    # Set only by the test session, and never written to environment.json.
    # This is a deliberate exception to "the file decides", scoped to one
    # process: without it the suite drops and recreates whichever database the
    # file happens to name, which on a day you had switched to prod means the
    # prod database. The file stays untouched and still reads `dev`.
    _process_override: str | None = None

    @staticmethod
    def use_for_this_process(environment: str) -> str:
        available = Environment.available()
        if environment not in available:
            raise Exception(f'no config.{environment}.json exists. '
                            f'Available: {available}')
        Environment._process_override = environment
        return environment

    @staticmethod
    def available() -> list[str]:
        """The environments that actually have a configuration file.

        Derived rather than listed, so `config.test.json` becoming a real file
        is the only step needed to make `test` a real environment.
        """
        return sorted(p.name[len('config.'):-len('.json')]
                      for p in CONFIG_DIRECTORY.glob('config.*.json'))

    @staticmethod
    def get() -> str:
        available = Environment.available()
        if Environment._process_override is not None:
            return Environment._process_override
        if not ENVIRONMENT_FILE.is_file():
            raise Exception(
                f'{ENVIRONMENT_FILE} not found. It is tracked in git, so this '
                f'means it was deleted.\n'
                f'Restore it, or create it holding one of {available}:\n'
                f'    {{ "environment": "dev" }}')
        try:
            environment = json.loads(ENVIRONMENT_FILE.read_text(encoding='utf-8'))['environment']
        except (ValueError, KeyError, TypeError) as e:
            raise Exception(f'{ENVIRONMENT_FILE} is not readable as '
                            f'{{"environment": "..."}}: {e}')

        if environment not in available:
            raise Exception(f'{ENVIRONMENT_FILE.name} says {environment!r}, '
                            f'which has no config.{environment}.json. '
                            f'Available: {available}')
        return environment
