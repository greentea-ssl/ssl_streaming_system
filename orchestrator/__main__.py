# main.py
import queue
import time
import argparse
import os
# orchestrator.py から Orchestrator クラスをインポート
from .orchestrator import Orchestrator
# event_listener.py から EventListener クラスをインポート
from .event_listener import EventListener
from common.config_loader import load_config
# (必要であれば、他のモジュールもインポート)

# --- ここに orchestrator.py から移動してきた if __name__ == '__main__': ブロックの内容を記述 ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(...)
    parser.add_argument(
        '--orchestrator-config', 
        type=str,
        default='../config/config_orchestrator.yaml', 
        help='Path to the orchestrator config file')
    parser.add_argument(
        '--priority-config', 
        type=str,
        default='../config/config_priority.yaml', 
        help='Path to the priority config file')
    args = parser.parse_args()

    # パス解決
    script_dir = os.path.dirname(__file__)
    orch_cfg_path = os.path.abspath(os.path.join(script_dir, args.orchestrator_config))
    prio_cfg_path = os.path.abspath(os.path.join(script_dir, args.priority_config))

    # ★ 設定ファイルをここで読み込む
    orchestrator_config_data = load_config(orch_cfg_path)
    priority_config_data = load_config(prio_cfg_path)

    # 読み込み成功チェック
    if orchestrator_config_data is None or priority_config_data is None:
        print("Error: Failed to load configuration files. Exiting.")
        exit(1)

    print("Starting commentary system (Listener + Orchestrator)...") # メッセージを修正
    message_queue = queue.Queue()

    # 環境変数からgcのマルチキャストグループ, ポート番号を取得
    multicast_group = os.environ.get('GC_MULTICAST_GROUP', '224.5.23.1')
    multicast_port = os.environ.get('GC_MULTICAST_PORT', '10003')
    # 整数にキャスト
    multicast_port = int(multicast_port)
    
    # リスナー起動
    listener = EventListener(message_queue, multicast_group=multicast_group, multicast_port=multicast_port)
    listener.start()

    # オーケストレーター起動
    orchestrator = Orchestrator(
        input_queue=message_queue,
        orchestrator_config=orchestrator_config_data,
        priority_config=priority_config_data
    )
    orchestrator.start()

    try:
        while listener.is_alive() and orchestrator.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping threads...")
    finally:
        # ... (終了処理 - listener.stop(), orchestrator.stop(), .join() など) ...
        print("All threads stopped.")