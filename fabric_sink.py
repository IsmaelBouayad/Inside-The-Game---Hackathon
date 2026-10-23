import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

FALLBACK_FILE = "fabric_local_fallback.jsonl"


class FabricTelemetrySink:
    """
    Streams live match alarms, verified overlays, director audit events, and metrics
    to Microsoft Fabric Eventstream (via Azure Event Hubs protocol), with automatic
    local JSONL fallback when running offline or in CI.
    """

    def __init__(self):
        self.conn_str = os.environ.get("EVENTHUB_CONNECTION_STRING", "").strip()
        self.live_enabled = False
        self._producer = None
        self.sent_live_count = 0
        self.local_fallback_count = 0

        if self.conn_str and "Endpoint=sb://" in self.conn_str and "<namespace>" not in self.conn_str:
            try:
                from azure.eventhub.aio import EventHubProducerClient
                self._producer = EventHubProducerClient.from_connection_string(conn_str=self.conn_str)
                self.live_enabled = True
            except Exception as e:
                print(f"⚠️ [Fabric Sink] Azure EventHub SDK init fallback ({e})")
                self.live_enabled = False

    async def ingest_record(self, record_type: str, payload: dict) -> str:
        envelope = {
            "record_type": record_type,
            "ingested_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "payload": payload
        }
        if self.live_enabled and self._producer is not None:
            try:
                from azure.eventhub import EventData
                batch = await self._producer.create_batch()
                batch.add(EventData(json.dumps(envelope, ensure_ascii=False)))
                await self._producer.send_batch(batch)
                self.sent_live_count += 1
                return "fabric_eventstream_live"
            except Exception as e:
                print(f"⚠️ [Fabric Sink] Live send fallback to local JSONL ({e})")

        self.local_fallback_count += 1
        with open(FALLBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        return "local_jsonl_fallback"

    async def close(self):
        if self._producer is not None:
            try:
                await self._producer.close()
            except Exception:
                pass
