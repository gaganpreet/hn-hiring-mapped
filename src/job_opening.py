"""Job Opening Module."""

class JobOpening(object):
    """Representation of a job opening."""

    _h1b_patterns = ['h1b', 'h1-b', 'h-1b']

    def __init__(self, text):
        text = text.lower()
        self._remote = ('remote' in text and 'no remote' not in text)
        self._h1b = (any(pattern in text
                         for pattern in self._h1b_patterns) and
                     all('no ' + pattern not in text
                         for pattern in self._h1b_patterns))
        self._intern = ('intern' in text)

    @property
    def remote(self):
        """Remote locations."""
        return self._remote

    @property
    def h1b(self):
        """H1B accepted."""
        return self._h1b

    @property
    def intern(self):
        """Intern position."""
        return self._intern

