import json
from pathlib import Path

"""------------------------------------------------------------------------------------------------
Key lookup is colon-separated: Configuration.get('database:url').

The source codebase gets this class from its own shared library. This
application has no such library, so it carries the smallest implementation with
the same surface -- rather than depending on someone else's package or inventing
a different call for the generator to make.
"""
class Configuration:
    _values = {}

    @classmethod
    def load(cls, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f'Configuration file not found: {path}')
        cls._values = json.loads(path.read_text(encoding='utf-8'))

    @classmethod
    def is_loaded(cls):
        return bool(cls._values)

    @classmethod
    def get(cls, key, default=None):
        node = cls._values
        for part in key.split(':'):
            if not isinstance(node, dict) or part not in node:
                if default is not None:
                    return default
                raise KeyError(f'Configuration key not found: {key}')
            node = node[part]
        return node
