"""Site settings cache — shared between web.py and API endpoints."""

_cache = {}
_cache_time = None


def get_cached_settings() -> dict:
    """Return current cached settings dict."""
    return _cache


def get_cache_time():
    return _cache_time


def set_cache(data: dict, ts):
    global _cache, _cache_time
    _cache = data
    _cache_time = ts


def is_cache_empty() -> bool:
    return not _cache


def invalidate_site_settings_cache():
    """Clear the site settings cache so next read fetches fresh data from DB."""
    global _cache, _cache_time
    _cache = {}
    _cache_time = None
