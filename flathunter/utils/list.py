"""Utility type for chunking lists."""

from collections.abc import Generator
from typing import TypeVar

CLT = TypeVar("CLT")

def chunk_list[CLT](list_var: list[CLT], size: int) -> Generator[list[CLT]]:
    """Split a list into the given chunk size
    :param l: input list
    :param size: output chunk size
    :return:
    """
    for i in range(0, len(list_var), size):
        yield list_var[i:i + size]
