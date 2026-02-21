class ToolCache:
    def __init__(self):
        self._store = {}

    def get(self, key: str):
        """Returns cached value or None if not found."""
        return self._store.get(key, None)

    def set(self, key: str, value: str):
        """Store a result against a key."""
        self._store[key] = value

    def has(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._store

# Single shared instance used across the session
tool_cache = ToolCache()