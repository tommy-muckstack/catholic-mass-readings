from __future__ import annotations

from typing import TYPE_CHECKING, cast

from bs4.element import Tag

if TYPE_CHECKING:
    from collections.abc import Iterable


def find_iter(parent: Tag, *, name: str | None = None, class_: str | None = None) -> Iterable[Tag]:
    container = parent.find(name=name, class_=class_)
    while container:
        yield cast(Tag, container)
        container = container.find_next(name=name, class_=class_)
