import datetime
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.chat import Chat
from app.db.models.memory_entry import MemoryEntry
from app.db.models.user import User
from app.services.memory.memory_service import MemoryService


@pytest.mark.asyncio
async def test_score_importance():
    service = MemoryService()

    # 0.5 base; +0.15 if len>200; -0.2 if len<50; +0.1 if digits present;
    # +0.25 if important words; -0.1 if question; cap [0.1, 1.0]

    # Test short text (<50 chars)
    short_text = "Hello world!"
    score = await service.score_importance(short_text)
    assert score == 0.3  # 0.5 base - 0.2 short

    # Test long text (>200 chars)
    long_text = (
        "This is a very long text designed to exceed two hundred characters in length. "
        "It needs to be sufficiently descriptive and verbose so that the length check "
        "in the importance scoring mechanism evaluates to true. Let's make sure it is long enough."
    )
    score = await service.score_importance(long_text)
    assert score == 0.65  # 0.5 base + 0.15 long

    # Test text containing digits
    digits_text = "I was born on July 4, 1776."  # 27 chars: 0.5 - 0.2 (short) + 0.1 (digits) = 0.4
    score = await service.score_importance(digits_text)
    assert score == pytest.approx(0.4)

    # Test text with important words
    pref_text = "My favorite color is green and I always prefer coffee over tea."
    # 63 chars: 0.5 base + 0.25 (prefer/always/favorite) = 0.75
    score = await service.score_importance(pref_text)
    assert score == 0.75

    # Test question
    question_text = "What is the CAP theorem?"
    # 24 chars: 0.5 base - 0.2 (short) - 0.1 (question) = 0.2
    score = await service.score_importance(question_text)
    assert score == pytest.approx(0.2)


@pytest.mark.asyncio
async def test_short_term_memory(monkeypatch):
    service = MemoryService()

    # Mock Redis client and make_key/set_json/get_json/delete
    mock_redis = MagicMock()
    mock_redis.make_key.return_value = "ai_os:short_term:user123:session456"
    mock_redis.set_json = AsyncMock()

    stored_data = None

    async def mock_get_json(key):
        return stored_data

    async def mock_set_json(key, val, ttl=None):
        nonlocal stored_data
        stored_data = val

    async def mock_delete(key):
        nonlocal stored_data
        stored_data = None

    mock_redis.get_json = mock_get_json
    mock_redis.set_json = mock_set_json
    mock_redis.delete = mock_delete

    # Patch get_redis
    monkeypatch.setattr(
        "app.services.memory.memory_service.get_redis", lambda: mock_redis
    )

    # Test store & get short term
    messages = [{"role": "user", "content": "hello"}]
    await service.store_short_term("user123", "session456", messages)
    res = await service.get_short_term("user123", "session456")
    assert res == messages

    # Test append_to_session
    new_msg = {"role": "assistant", "content": "how can I help?"}
    await service.append_to_session("user123", "session456", new_msg)
    res = await service.get_short_term("user123", "session456")
    assert len(res) == 2
    assert res[1] == new_msg

    # Test truncation to MAX_MSGS
    for i in range(25):
        await service.append_to_session(
            "user123", "session456", {"role": "user", "content": f"msg {i}"}
        )
    res = await service.get_short_term("user123", "session456")
    assert len(res) == service.MAX_MSGS
    assert res[-1]["content"] == "msg 24"

    # Test clear_session
    await service.clear_session("user123", "session456")
    res = await service.get_short_term("user123", "session456")
    assert res == []
