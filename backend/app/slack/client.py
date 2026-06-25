import logging
import httpx
import json
import os
from datetime import datetime
from app.config import settings

logger = logging.getLogger("forgeos.slack")


class SlackClient:
    """
    Handles all Slack interactions for ForgeOS:
    - Outbound: post_message() delivers to local JSON log and optionally a real Slack webhook.
    - Event logging: log_event() appends a structured event to the event_log store.
    """

    def __init__(self):
        self.channel_log_path = os.path.join(settings.DATA_DIR, "slack_channels.json")
        self._initialize_channels()

    def _initialize_channels(self):
        initial_channels = {
            "#sprint-main": [],
            "#agent-developer": [],
            "#agent-security": [],
            "#agent-qa": [],
            "#agent-docs": [],
            "#ci-cd": [],
            "#analytics": [],
            "#human-review": [],
            "#system-health": [],
            "#agent-log": [],
        }
        if not os.path.exists(self.channel_log_path):
            with open(self.channel_log_path, "w") as f:
                json.dump(initial_channels, f, indent=4)
        else:
            try:
                with open(self.channel_log_path, "r") as f:
                    data = json.load(f)
                updated = False
                for chan in initial_channels:
                    if chan not in data:
                        data[chan] = []
                        updated = True
                if updated:
                    with open(self.channel_log_path, "w") as f:
                        json.dump(data, f, indent=4)
            except Exception:
                pass

    def get_channel_history(self, channel: str) -> list:
        try:
            with open(self.channel_log_path, "r") as f:
                channels = json.load(f)
                return channels.get(channel, [])
        except Exception:
            return []

    async def post_message(self, channel: str, message: str) -> bool:
        """
        Delivers a message to a channel:
        1. Persists it locally in slack_channels.json for dashboard streaming.
        2. Sends to the real Slack webhook if SLACK_WEBHOOK_URL is configured
           (always, regardless of SIMULATION_MODE — the webhook is opt-in by configuration).
        """
        logger.info(f"[SLACK] [{channel}] {message}")
        timestamp = datetime.utcnow().isoformat()

        # 1. Persist locally
        try:
            with open(self.channel_log_path, "r") as f:
                channels = json.load(f)

            if channel not in channels:
                channels[channel] = []

            channels[channel].append({
                "timestamp": timestamp,
                "message": message,
                "sender": "ForgeOS Agents",
            })

            # Keep each channel to 200 entries max
            if len(channels[channel]) > 200:
                channels[channel] = channels[channel][-200:]

            with open(self.channel_log_path, "w") as f:
                json.dump(channels, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to persist Slack message locally: {e}")

        # 2. Forward to real Slack webhook if configured
        if settings.SLACK_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.post(
                        settings.SLACK_WEBHOOK_URL,
                        json={"text": f"*{channel}*\n{message}"},
                    )
                    if res.status_code != 200:
                        logger.warning(
                            f"Slack webhook returned non-200 status {res.status_code}: {res.text}"
                        )
                    return res.status_code == 200
            except Exception as e:
                logger.error(f"Failed to deliver Slack webhook message: {e}")

        return True

    def log_event(self, source: str, event_type: str, payload: str, task_id: str = "") -> None:
        """
        Appends a structured pipeline event to the event_log store.
        This is the single write-path for the Live Event Console.
        """
        try:
            from app.db.store import event_log_store
            event = event_log_store.append_event(
                source=source,
                event_type=event_type,
                payload=payload,
                task_id=task_id,
            )
            logger.info(
                f"[EVENT] [{source}] [{event_type}] {payload}"
                + (f" (task={task_id})" if task_id else "")
            )
        except Exception as e:
            logger.error(f"Failed to log event: {e}")


slack_client = SlackClient()
