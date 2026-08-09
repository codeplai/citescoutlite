"""
Integraciones externas: rate-limiting, robots.txt, web fetching.
"""

from .rate_limiter import (
    RateLimiter,
    check_rate_limit,
    rate_limit_status,
    record_request_success,
    record_request_failure,
)
from .robots_parser import (
    RobotsParser,
    check_robots_txt,
    get_crawl_delay,
    get_robots_cache_status,
    close_robots_parser,
)

__all__ = [
    "RateLimiter",
    "check_rate_limit",
    "rate_limit_status",
    "record_request_success",
    "record_request_failure",
    "RobotsParser",
    "check_robots_txt",
    "get_crawl_delay",
    "get_robots_cache_status",
    "close_robots_parser",
]
