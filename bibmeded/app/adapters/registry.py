"""Adapter registry — auto-discovers any BaseSourceAdapter subclass under
``app/adapters/``.

**For contributors writing a new adapter**: drop a module here, subclass
``BaseSourceAdapter``, set ``name``, ``display_name``, and ``requires_api_key``,
and you're done. There is NO ``__init__.py`` registration step, no schema
change, and no frontend update needed — the ``/api/adapters`` route reads
from this registry at request time and the frontend fetches it dynamically.
"""

import importlib
import pkgutil

from app.adapters.base import BaseSourceAdapter

_adapters: dict[str, type[BaseSourceAdapter]] = {}


def discover_adapters() -> None:
    """Scan ``app/adapters/`` for ``BaseSourceAdapter`` subclasses and populate
    the registry. Called lazily on first ``get_adapter`` / ``list_adapters``."""
    import app.adapters as pkg

    for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        if module_name in ("base", "registry"):
            continue
        module = importlib.import_module(f"app.adapters.{module_name}")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, BaseSourceAdapter)
                and attr is not BaseSourceAdapter
            ):
                _adapters[attr.name] = attr


def get_adapter(name: str, **kwargs) -> BaseSourceAdapter:
    if not _adapters:
        discover_adapters()
    if name not in _adapters:
        raise ValueError(f"Unknown adapter: {name}. Available: {list(_adapters.keys())}")
    return _adapters[name](**kwargs)


def list_adapters() -> list[dict]:
    if not _adapters:
        discover_adapters()
    return [
        {
            "name": cls.name,
            "display_name": cls.display_name,
            "requires_api_key": cls.requires_api_key,
        }
        for cls in _adapters.values()
    ]
