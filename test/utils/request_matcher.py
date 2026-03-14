"""Test helper for counting matched requests."""

class RequestCounter:
    """Test helper class for counting matched requests."""

    def __init__(self) -> None:
        """Initialise counter to zero."""
        self.i = 0

    def count(self, request) -> bool: # pylint: disable=unused-argument
        """Increment counter."""
        self.i += 1
        return True
