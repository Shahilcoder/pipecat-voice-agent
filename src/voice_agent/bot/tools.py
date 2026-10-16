from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pipecat.services.llm_service import FunctionCallParams


async def get_current_time(params: FunctionCallParams, timezone: str) -> None:
    """Get the current date and time in a timezone.

    Args:
        timezone: IANA timezone name, e.g. "Europe/London" or "Asia/Kolkata".
    """
    try:
        now = datetime.now(ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError):
        await params.result_callback({"error": f"Unknown timezone: {timezone}"})
        return

    await params.result_callback(
        {"timezone": timezone, "current_time": now.isoformat(timespec="minutes")}
    )


TOOLS = [get_current_time]
