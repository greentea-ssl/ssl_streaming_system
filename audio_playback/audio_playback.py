# playback_module.py
import zmq
import json
import time
import threading
from typing import Optional, Dict, Any
# --- データモデルをインポート ---
try:
    from common.data_models import GameEvent # 作成したデータモデル
except ImportError:
    print("Error: data_models.py not found.")
    exit(1)
# --- ここまで ---


class AudioPlaybackModule:
    def __init__(self, 
                 audio_config: Dict[str, Any]):
        
        self.audio_config = audio_config
        zmq_publisher_uri = audio_config.get("zmq_publisher_uri", "tcp://localhost:5555")

        if "event_actions" not in self.audio_config:
             self.audio_config["event_actions"] = {}
        if "DEFAULT_ACTION" not in self.audio_config:
             self.audio_config["DEFAULT_ACTION"] = {"action": "ignore"}

        self.zmq_publisher_uri = zmq_publisher_uri
        self.context = zmq.Context()
        self.subscriber: Optional[zmq.Socket] = None
        self._stop_event = threading.Event() # プロセスだが便宜上流用
        print(f"Playback Module initialized, connecting to {self.zmq_publisher_uri}")

    def _connect_subscriber(self):
        """Subscriberソケットを(再)接続する"""
        if self.subscriber:
            self.subscriber.close()
        self.subscriber = self.context.socket(zmq.SUB)
        # 再接続時の待機時間を設定 (例: 1秒)
        self.subscriber.setsockopt(zmq.RCVTIMEO, 1000)
        # event トピックを購読 (バイト列で指定)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b"event")
        self.subscriber.connect(self.zmq_publisher_uri)
        print(f"Playback Module connected to {self.zmq_publisher_uri} and subscribed to 'event'")

    def stop(self):
        self._stop_event.set()
        print("Playback Module stop requested.")

    def run(self):
        print("Playback Module starting...")
        self._connect_subscriber()

        while not self._stop_event.is_set():
            if self.subscriber is None:
                 print("Subscriber socket is None, attempting to reconnect...")
                 time.sleep(2)
                 self._connect_subscriber()
                 continue

            try:
                # マルチパートメッセージを受信
                topic, payload = self.subscriber.recv_multipart()

                # print(f"Received message on topic: {topic.decode()}") # デバッグ

                if topic == b"event":
                    try:
                        json_str = payload.decode('utf-8')
                        game_event = GameEvent.from_json(json_str)
                        # --- ここで受信したイベントを処理 ---
                        # ミニマル版ではコンソールに表示するだけ
                        print(f"Playback Module Received GameEvent:")
                        print(f"  Timestamp: {game_event.timestamp}")
                        print(f"  Type:      {game_event.event_type}")
                        print(f"  Priority:  {game_event.priority}")
                        print(f"  Data:      {game_event.data}")
                        print("-" * 10)
                        # ------------------------------------
                    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as e:
                        print(f"Playback Module: Error decoding event payload: {e}")
                    except Exception as e:
                        print(f"Playback Module: Unexpected error processing event: {e}")

            except zmq.Again:
                # RCVTIMEOによるタイムアウト、正常。stop()チェックのため。
                continue
            except zmq.ZMQError as e:
                print(f"Playback Module: ZeroMQ Error: {e}")
                print("Attempting to reconnect...")
                time.sleep(2) # 再接続前に少し待つ
                self._connect_subscriber() # 接続試行
            except Exception as e:
                 print(f"Playback Module: Unexpected error: {e}")
                 time.sleep(1)


        # --- 終了処理 ---
        print("Playback Module shutting down...")
        if self.subscriber:
            self.subscriber.close()
        self.context.term()
        print("Playback Module ZeroMQ context terminated.")