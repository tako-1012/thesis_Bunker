"""
Lightweight search node used by AHA* variants.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(order=True)
class SearchNode:
    f: float
    position: Tuple[int, int, int] = field(compare=False)
    g: float = field(default=0.0, compare=False)
    h: float = field(default=0.0, compare=False)
    parent: Optional["SearchNode"] = field(default=None, compare=False)

    def __post_init__(self) -> None:
        if self.f == 0.0:
            self.f = self.g + self.h
