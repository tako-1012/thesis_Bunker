"""bunker_3d_nav.path_planner_3d shim package.

This package provides lightweight shims for tests. The actual
`cost_function` submodule is implemented in the sibling file
`cost_function.py` which loads the repository implementation or a
deterministic fallback. Avoid importing the upstream package here to
prevent import-time side effects.
"""

__all__ = []
