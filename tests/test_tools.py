from unittest.mock import AsyncMock

from voice_agent.bot.tools import get_current_time


async def test_get_current_time_returns_time_for_valid_timezone() -> None:
    params = AsyncMock()
    await get_current_time(params, "Europe/London")
    result = params.result_callback.await_args.args[0]
    assert result["timezone"] == "Europe/London"
    assert "current_time" in result


async def test_get_current_time_reports_unknown_timezone() -> None:
    params = AsyncMock()
    await get_current_time(params, "Mars/Olympus_Mons")
    result = params.result_callback.await_args.args[0]
    assert "error" in result
