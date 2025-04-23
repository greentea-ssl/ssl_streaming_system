# main.py
import queue
import time
# orchestrator.py から Orchestrator クラスをインポート
from .orchestrator import Orchestrator
# event_listener.py から EventListener クラスをインポート
from .event_listener import EventListener
# (必要であれば、他のモジュールもインポート)

# --- ここに orchestrator.py から移動してきた if __name__ == '__main__': ブロックの内容を記述 ---
if __name__ == '__main__':
    print("Starting commentary system (Listener + Orchestrator)...") # メッセージを修正
    message_queue = queue.Queue()

    # リスナー起動
    # listener = EventListener(message_queue, interface_ip='YOUR_INTERFACE_IP')
    listener = EventListener(message_queue)
    listener.start()

    # オーケストレーター起動
    # orchestrator = Orchestrator(message_queue, zmq_publisher_uri="tcp://*:5556") # URI変更例
    orchestrator = Orchestrator(message_queue)
    orchestrator.start()

    try:
        while listener.is_alive() and orchestrator.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping threads...")
    finally:
        # ... (終了処理 - listener.stop(), orchestrator.stop(), .join() など) ...
        print("All threads stopped.")