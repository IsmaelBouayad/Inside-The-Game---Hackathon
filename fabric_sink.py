import json
import os
import asyncio
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

FALLBACK_FILE = "fabric_local_fallback.jsonl"

class FabricTelemetrySink:
    """
    Connecteur hybride Microsoft Fabric Eventstream (via Azure Event Hubs SDK).
    - Si EVENTHUB_CONNECTION_STRING est configuré dans .env : envoi réseau réel vers Fabric.
    - Sinon : écriture locale dans fabric_local_fallback.jsonl (mode hors-ligne / CI).
    """
    def __init__(self):
        self.conn_str = os.environ.get("EVENTHUB_CONNECTION_STRING", "").strip()
        self.live_enabled = False
        self._producer = None

        if self.conn_str and "Endpoint=sb://" in self.conn_str:
            try:
                from azure.eventhub.aio import EventHubProducerClient
                from azure.eventhub import EventData
                self._EventData = EventData
                self._producer = EventHubProducerClient.from_connection_string(self.conn_str)
                self.live_enabled = True
            except Exception as e:
                print(f"⚠️ [FabricSink] SDK Azure EventHub non disponible ({e}), repli local activé.")

    async def ingest_record(self, record_type: str, payload: dict) -> str:
        record = {
            "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
            "record_type": record_type,
            "delivery_mode": "fabric_eventstream_live" if self.live_enabled else "local_jsonl_fallback",
            "data": payload
        }

        if self.live_enabled and self._producer is not None:
            try:
                batch = await self._producer.create_batch()
                batch.add(self._EventData(json.dumps(record, ensure_ascii=False)))
                await self._producer.send_batch(batch)
                return "fabric_eventstream_live"
            except Exception as e:
                record["delivery_mode"] = f"local_fallback_after_error ({type(e).__name__})"

        with open(FALLBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        await asyncio.sleep(0)
        return record["delivery_mode"]

    async def close(self):
        if self._producer is not None:
            try:
                await self._producer.close()
            except Exception:
                pass
