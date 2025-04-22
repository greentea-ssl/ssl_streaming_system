# orchestrator.py
import queue
import threading
import time
import zmq
import json

# --- データモデルとProtobuf Enumをインポート ---
try:
    from common.data_models import GameEvent, Team # 作成したデータモデル
except ImportError:
    print("Error: data_models.py not found.")
    exit(1)

try:
    from state import ssl_gc_referee_message_pb2 as referee_pb2
except ImportError:
    print("Error: Protobuf generated code not found.")
    exit(1)
# --- ここまで ---


class Orchestrator(threading.Thread):
    def __init__(self,
                 input_queue: queue.Queue,
                 zmq_publisher_uri: str = "tcp://*:5555"):
        super().__init__(daemon=True)
        self.input_queue = input_queue
        self.zmq_publisher_uri = zmq_publisher_uri
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.previous_command: Optional[int] = None # ProtobufのEnum値で保持
        self._stop_event = threading.Event()
        print(f"Orchestrator initialized, publishing to {self.zmq_publisher_uri}")

    def stop(self):
        self._stop_event.set()
        print("Orchestrator stop requested.")

    def run(self):
        print("Orchestrator thread started.")
        try:
            self.publisher.bind(self.zmq_publisher_uri)
            print(f"Orchestrator bound to {self.zmq_publisher_uri}")
        except zmq.ZMQError as e:
            print(f"Error binding ZeroMQ socket: {e}")
            return # スレッド終了

        while not self._stop_event.is_set():
            try:
                # キューからRefereeメッセージを取得 (ブロッキング)
                ref_msg: referee_pb2.Referee = self.input_queue.get(timeout=1.0)

                current_command = ref_msg.command

                # --- イベント検出ロジック (ミニマル版) ---
                if current_command != self.previous_command:
                    print(f"Orchestrator: Command changed from {self.previous_command} to {current_command}") # デバッグ

                    # COMMAND_STOP に変化した場合のみイベントを生成
                    if current_command == referee_pb2.Referee.STOP:
                        print("Orchestrator: Detected COMMAND_STOP")
                        game_event = GameEvent(
                            event_type="COMMAND_STOP",
                            priority=5, # 固定値
                            data={}     # STOPコマンドはデータなし
                        )

                        # --- イベントをJSONにしてPublish ---
                        try:
                            json_payload = game_event.to_json()
                            # トピック名を指定して送信 (バイト列にする必要あり)
                            self.publisher.send_multipart([
                                b"event",  # トピック名 (bytes)
                                json_payload.encode('utf-8') # ペイロード (bytes)
                            ])
                            print(f"Orchestrator: Published event: {game_event.event_type}")
                        except Exception as e:
                            print(f"Orchestrator: Error publishing event: {e}")

                    # 他のイベントは無視

                    # 状態を更新
                    self.previous_command = current_command

                # キューの処理完了を通知 (get()の完了を示す)
                self.input_queue.task_done()

            except queue.Empty:
                # タイムアウトは正常、stop()をチェックするため
                continue
            except Exception as e:
                print(f"Orchestrator: Error processing message from queue: {e}")
                # 不明なエラーが発生しても継続試行
                time.sleep(1)

        # --- 終了処理 ---
        print("Orchestrator shutting down...")
        self.publisher.close()
        self.context.term()
        print("Orchestrator ZeroMQ context terminated.")


# --- ListenerとOrchestratorを連携させるメイン部分 ---
# (listener.py をインポートするか、1つのファイルにまとめる)
from event_listener import EventListener # listener.py がある前提

if __name__ == '__main__':
    print("Starting integrated test (Listener + Orchestrator)...")
    message_queue = queue.Queue()

    # リスナー起動
    listener = EventListener(message_queue) # 必要なら interface_ip を指定
    listener.start()

    # オーケストレーター起動
    orchestrator = Orchestrator(message_queue)
    orchestrator.start()

    try:
        # メインスレッドはスレッド終了を待つだけ
        # Ctrl+Cで終了させる
        while listener.is_alive() and orchestrator.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping threads...")
    finally:
        listener.stop()
        orchestrator.stop()
        listener.join()
        orchestrator.join()
        print("All threads stopped.")