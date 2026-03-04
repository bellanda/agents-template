from collections.abc import Mapping


class PromptCache:
    _cache: Mapping[str, str] = {}

    @classmethod
    def get(cls, key: str):
        return cls._cache.get(key)

    @classmethod
    def set(cls, key: str, value: str):
        cls._cache[key] = value


prompt_cache = PromptCache()
