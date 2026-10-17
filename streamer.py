import json
import time
import argparse
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class FabricSink:
    """Optional subscriber that pushes events to Microsoft Fabric via Event Hubs."""
    def __init__(self):
        conn_str = os.environ.get("EVENTHUB_CONNECTION_STRING")
        if not conn_str:
            raise ValueError("❌ EVENTHUB_CONNECTION_STRING not found in .env")
            
        from azure.eventhub import EventHubProducerClient
        self.producer = EventHubProducerClient.from_connection_string(conn_str=conn_str)
        print("🔗 FabricSink: Connected to Microsoft Fabric Eventstream.")

    def __call__(self, event):
        from azure.eventhub import EventData
        batch = self.producer.create_batch()
        batch.add(EventData(json.dumps(event)))
        self.producer.send_batch(batch)

class TerminalSink:
    """Simple subscriber to print events for testing."""
    def __call__(self, event):
        print(f"[STREAM] Min {event['minute']} | {event['team']} | {event['event_type']} (ID: {event['event_id']})")

class MatchStreamer:
    def __init__(self, filepath, speed=30.0):
        self.filepath = filepath
        self.speed = float(speed)
        self.subscribers = []

    def subscribe(self, callback):
        self.subscribers.append(callback)

    def run(self):
        print(f"▶️ Playing {self.filepath} at {self.speed}x speed...")
        last_dt = None
        events_processed = 0
        
        with open(self.filepath, "r") as f:
            for line in f:
                event = json.loads(line)
                current_dt = datetime.fromisoformat(event["timestamp"])
                
                # Calculate sleep time based on deterministic simulated timestamps
                if last_dt and self.speed > 0:
                    delta_sec = (current_dt - last_dt).total_seconds()
                    if delta_sec > 0:
                        time.sleep(delta_sec / self.speed)
                        
                last_dt = current_dt
                events_processed += 1
                
                # Broadcast to all subscribers
                for sub in self.subscribers:
                    sub(event)
                    
        print(f"⏹️ Stream ended. {events_processed} events processed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, default="match_events.jsonl")
    parser.add_argument("--speed", type=float, default=30.0, help="0=instant, 1=realtime, 30=fast")
    parser.add_argument("--emit-fabric", action="store_true", help="Enable Fabric Event Hub sink")
    args = parser.parse_args()

    streamer = MatchStreamer(args.file, args.speed)
    
    # Register basic UI/Terminal subscriber
    streamer.subscribe(TerminalSink())
    
    # Register Fabric subscriber if flag is passed
    if args.emit_fabric:
        try:
            streamer.subscribe(FabricSink())
        except Exception as e:
            print(e)
            
    streamer.run()
