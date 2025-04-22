# main.py
import queue
import threading
import time
import signal
import sys
import os # 設定ファイルのパス解決用

# 他のモジュールをインポート
from orchestrator.event_listener import EventListener
from orchestrator.orchestrator import Orchestrator
from audio_playback.audio_playback import AudioPlaybackModule

# 設定ファイルのパス (環境に合わせて変更)
# カレントディレクトリに設定ファイルがあると仮定
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_ORCHESTRATOR = os.path.join(CONFIG_DIR, "config_orchestrator.yaml")
CONFIG_PRIORITY = os.path.join(CONFIG_DIR, "config_priority.yaml")
CONFIG_AUDIO = os.path.join(CONFIG_DIR, "config_audio.yaml")

# SSL設定 (環境に合わせて変更)
MULTICAST_IP = "224.5.23.1"
MULTICAST_PORT = 10003
# 特定NICから受信する場合は、そのIPアドレスを文字列で指定
# LISTENING_INTERFACE_IP = "192.168.1.100"
LISTENING_INTERFACE_IP = None # Noneの場合はシステムに任せる (or "")


# グローバルな停止フラグ
stop_flag = threading.Event()

def signal_handler(sig, frame):
    print('Shutdown signal received!')
    stop_flag.set()

if __name__ == "__main__":
    print("Starting SSL Commentary System...")

    # 終了シグナルハンドラ設定
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 1. 連携用キューの作成
    referee_queue = queue.Queue()

    # 2. 各コンポーネントの初期化
    # リスナー設定 (必要に応じて interface_ip を設定)
    listener = EventListener(MULTICAST_IP, MULTICAST_PORT, referee_queue, interface_ip=LISTENING_INTERFACE_IP)

    # オーケストレーター設定
    orchestrator = Orchestrator(referee_queue, CONFIG_ORCHESTRATOR, CONFIG_PRIORITY)

    # 音声再生モジュール設定 (オーケストレーターのURIを取得する方法が必要)
    # ここでは config_orchestrator.yaml から読み込む前提とする (要調整)
    import yaml
    publisher_uri = "tcp://127.0.0.1:5555" # デフォルト、または設定から読む
    try:
        with open(CONFIG_ORCHESTRATOR, 'r') as f:
            orch_conf = yaml.safe_load(f)
            publisher_uri = orch_conf.get('zmq_publisher_uri', publisher_uri)
    except Exception as e:
        print(f"Warning: Could not read orchestrator URI from config, using default: {publisher_uri}. Error: {e}")

    audio_player = AudioPlaybackModule(publisher_uri, CONFIG_AUDIO)

    # 3. 各コンポーネントのスレッド起動
    print("Starting components...")
    listener.start()
    # オーケストレーターのrunはブロッキングするので別スレッドで
    orchestrator_thread = threading.Thread(target=orchestrator.run, daemon=True)
    orchestrator_thread.start()
    # 音声再生モジュールも別プロセスまたはスレッドで開始 (ここではスレッド)
    audio_player.start()

    # 4. メインループ (終了待機)
    print("System running. Press Ctrl+C to exit.")
    while not stop_flag.is_set():
        try:
            # メインスレッドはここで待機 or 他の処理
            time.sleep(1)
        except KeyboardInterrupt: # Ctrl+C でも停止できるように
            print("KeyboardInterrupt received.")
            stop_flag.set()

    # 5. 終了処理
    print("Shutting down components...")
    listener.stop()
    orchestrator.stop()
    audio_player.stop()

    # スレッドの終了を待つ
    listener.join(timeout=2)
    orchestrator_thread.join(timeout=2)
    # audio_player の start がスレッドを開始する場合、それもjoinする
    # (現在のAudioPlaybackModule.start()はブロッキングしないので不要だが、
    #  _receive_thread と _reconnect_thread の join は stop() 内で行う想定)

    print("System exited.")