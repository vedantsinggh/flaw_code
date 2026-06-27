import logging
import httpx
import json
import os
from datetime import datetime
from app.config import settings

logger = logging.getLogger("forgeos.slack")


class SlackClient:
    """
    Handles all Slack interactions for OpenFlaw:
    - Outbound: post_message() delivers to local JSON log and optionally a real Slack webhook.
    - Event logging: log_event() appends a structured event to the event_log store.
    """

    def __init__(self):
        self.channel_log_path = os.path.join(settings.DATA_DIR, "slack_channels.json")
        self._initialize_channels()

    def _initialize_channels(self):
        initial_channels = {
            "#sprint-main": [],
            "#agent-coder": [],
            "#agent-log": [],
            "#ci-cd": [],
            "#human-review": [],
            "#agent-developer": [],
            "#agent-security": [],
            "#agent-qa": [],
            "#agent-docs": [],
            "#analytics": [],
            "#system-health": [],
            "#agent-orchestrator": [],
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

    async def post_message(
        self,
        channel: str,
        message: str,
        sender: str = "OpenFlaw Agents",
        receiver: str = "all",
        agent: str = "System",
        selected_model: str = "N/A",
        execution_duration: str = "N/A",
        status: str = "success",
        errors: str = "N/A"
    ) -> bool:
        """
        Delivers a message to a channel:
        1. Persists it locally in slack_channels.json for dashboard streaming.
        2. Sends to the real Slack webhook if SLACK_WEBHOOK_URL is configured.
        3. Appends a structured log entry in backend logs.
        """
        # Resolve mapped channel if settings available
        mapped_channel = settings.get_slack_channel(channel)
        logger.info(f"[SLACK] [{mapped_channel}] {message}")
        timestamp = datetime.utcnow().isoformat()

        # 1. Persist locally
        try:
            with open(self.channel_log_path, "r") as f:
                channels = json.load(f)

            if mapped_channel not in channels:
                channels[mapped_channel] = []

            channels[mapped_channel].append({
                "timestamp": timestamp,
                "message": message,
                "sender": sender,
            })

            # Keep each channel to 200 entries max
            if len(channels[mapped_channel]) > 200:
                channels[mapped_channel] = channels[mapped_channel][-200:]

            with open(self.channel_log_path, "w") as f:
                json.dump(channels, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to persist Slack message locally: {e}")

        # 2. Forward to real Slack webhook if configured
        webhook_sent = True
        if settings.SLACK_WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    res = await client.post(
                        settings.SLACK_WEBHOOK_URL,
                        json={"text": f"*{mapped_channel}*\n{message}"},
                    )
                    if res.status_code != 200:
                        logger.warning(
                            f"Slack webhook returned non-200 status {res.status_code}: {res.text}"
                        )
                        webhook_sent = (res.status_code == 200)
                    else:
                        webhook_sent = True
            except Exception as e:
                logger.error(f"Failed to deliver Slack webhook message: {e}")
                webhook_sent = False

        # 3. Log event in backend logs
        try:
            log_entry = {
                "timestamp": timestamp,
                "channel": mapped_channel,
                "sender": sender,
                "receiver": receiver,
                "agent": agent,
                "selected_model": selected_model,
                "execution_duration": execution_duration,
                "status": status,
                "errors": errors if errors != "N/A" else (None if webhook_sent else "webhook_failed")
            }
            backend_log_path = os.path.join(settings.DATA_DIR, "backend_slack_events.json")
            data = []
            if os.path.exists(backend_log_path):
                try:
                    with open(backend_log_path, "r") as lf:
                        data = json.load(lf)
                except Exception:
                    data = []
            data.append(log_entry)
            if len(data) > 1000:
                data = data[-1000:]
            with open(backend_log_path, "w") as lf:
                json.dump(data, lf, indent=4)
        except Exception as e:
            logger.error(f"Failed to write to backend_slack_events.json: {e}")

        return webhook_sent

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
            # Log this event to backend logs as well
            timestamp = datetime.utcnow().isoformat()
            log_entry = {
                "timestamp": timestamp,
                "channel": "event-log",
                "sender": source,
                "receiver": "system",
                "agent": source,
                "selected_model": "N/A",
                "execution_duration": "N/A",
                "status": "success",
                "errors": None
            }
            backend_log_path = os.path.join(settings.DATA_DIR, "backend_slack_events.json")
            data = []
            if os.path.exists(backend_log_path):
                try:
                    with open(backend_log_path, "r") as lf:
                        data = json.load(lf)
                except Exception:
                    data = []
            data.append(log_entry)
            if len(data) > 1000:
                data = data[-1000:]
            with open(backend_log_path, "w") as lf:
                json.dump(data, lf, indent=4)
        except Exception as e:
            logger.error(f"Failed to log event: {e}")


slack_client = SlackClient()
