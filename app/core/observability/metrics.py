import typing

from prometheus_client import (CONTENT_TYPE_LATEST, Counter, Gauge, Histogram,
                               generate_latest)

# HTTP
HTTP_REQUESTS = Counter(
    "ai_os_http_requests_total", "Total requests", ["method", "endpoint", "status"]
)
HTTP_LATENCY = Histogram(
    "ai_os_http_latency_seconds",
    "Request latency",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
)

# LLM
LLM_TOKENS = Counter(
    "ai_os_llm_tokens_total", "LLM tokens used", ["agent", "direction"]
)  # direction: prompt|completion|total
LLM_LATENCY = Histogram(
    "ai_os_llm_latency_seconds",
    "LLM call latency",
    ["agent", "model"],
    buckets=[0.5, 1, 2, 3, 5, 10, 20, 30, 60],
)
LLM_ERRORS = Counter("ai_os_llm_errors_total", "LLM API errors", ["error_type"])

# Tasks
TASKS_TOTAL = Counter("ai_os_tasks_total", "Tasks processed", ["type", "status"])
TASK_LATENCY = Histogram(
    "ai_os_task_latency_seconds",
    "Task duration",
    ["type", "agent"],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120],
)

# WebSocket
WS_CONNECTIONS = Gauge("ai_os_ws_connections_active", "Active WS connections")
WS_MESSAGES = Counter("ai_os_ws_messages_total", "WS messages", ["direction"])

# Documents & Memory
DOCS_PROCESSED = Counter(
    "ai_os_docs_processed_total", "Docs indexed", ["file_type", "status"]
)
MEMORIES_STORED = Counter("ai_os_memories_stored_total", "Long-term memories stored")

# CRITICAL: NEVER use user_id, session_id, UUID as label — causes cardinality explosion


def record_request(method: str, path: str, status: int, duration: float) -> typing.Any:
    """
    Automatically generated docstring.
    """
    normalized = _normalize_path(path)
    HTTP_REQUESTS.labels(method=method, endpoint=normalized, status=str(status)).inc()
    HTTP_LATENCY.labels(method=method, endpoint=normalized).observe(duration)


def _normalize_path(path: str) -> str:
    import re

    # Replace UUIDs with {id}
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "{id}", path
    )
    # Replace numeric segments with {n}
    path = re.sub(r"/\d+", "/{n}", path)
    return path


def get_metrics() -> tuple[bytes, str]:
    """
    Automatically generated docstring.
    """
    return generate_latest(), CONTENT_TYPE_LATEST
