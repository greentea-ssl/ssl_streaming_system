# dummy_sender.py
import socket
import time
import struct

# --- Protobufの生成済みコードをインポート ---
# (実際のパスに合わせて修正してください)
try:
    from state import ssl_gc_referee_message_pb2 as referee_pb2
except ImportError:
    print("Error: Protobuf generated code not found.")
    print("Please generate Python code from .proto files using protoc.")
    exit(1)
# --- ここまで ---

# 送信先マルチキャスト設定 (EventListenerのデフォルトに合わせる)
MULTICAST_GROUP = "224.5.23.1"
MULTICAST_PORT = 10003

# --- 送信するダミーRefereeメッセージを作成 ---

def create_referee_message(stage, command) -> referee_pb2.Referee:
    """指定されたStageとCommandを持つRefereeメッセージを作成"""
    msg = referee_pb2.Referee()
    # time モジュールから取得したUnixタイムスタンプ（秒）をマイクロ秒に変換
    current_unix_time_sec = time.time()
    msg.command_timestamp = int(current_unix_time_sec * 1_000_000) # Protobufは uint64 (microseconds) を想定
    msg.packet_timestamp = int(current_unix_time_sec * 1_000_000) # Protobufは uint64 (microseconds) を想定
    msg.command_counter = 0 # 初期値
    msg.yellow.name = "DummyYellow" # ダミーのチーム名
    msg.yellow.score = 0 # スコア初期値
    msg.yellow.red_cards = 0 # レッドカード初期値
    msg.yellow.yellow_cards = 0 # イエローカード初期値
    msg.yellow.yellow_card_times.extend([0, 0]) # イエローカードの時間初期値
    msg.yellow.timeout_time = 0 # タイムアウト時間初期値
    msg.yellow.timeouts = 0 # タイムアウト数初期値
    msg.yellow.goalkeeper = 0 # ゴールキーパー初期値
    msg.yellow.foul_counter = 0 # ファウルカウンター初期値
    msg.yellow.max_allowed_bots = 6 # 最大許容ロボット数初期値
    msg.blue.name = "DummyBlue" # ダミーのチーム名
    msg.blue.score = 0 # スコア初期値
    msg.blue.red_cards = 0 # レッドカード初期値
    msg.blue.yellow_cards = 0 # イエローカード初期値
    msg.blue.yellow_card_times.extend([0, 0]) # イエローカードの時間初期値
    msg.blue.timeout_time = 0 # タイムアウト時間初期値
    msg.blue.goalkeeper = 0 # ゴールキーパー初期値
    msg.blue.timeouts = 0 # タイムアウト数初期値


    msg.stage = stage
    msg.command = command
    # 他のフィールドはデフォルト値のままでも、テスト目的なら動作することが多い
    # 必要に応じて TeamInfo なども設定可能
    # msg.yellow.name = "DummyYellow"
    # msg.blue.name = "DummyBlue"
    return msg

# 1. 通常状態 (例: FORCE_START) のメッセージ
ref_msg_normal = create_referee_message(
    stage=referee_pb2.Referee.NORMAL_FIRST_HALF, # ステージは適宜変更
    command=referee_pb2.Referee.FORCE_START
)

# 2. STOP状態のメッセージ
ref_msg_stop = create_referee_message(
    stage=referee_pb2.Referee.NORMAL_FIRST_HALF, # Stageは同じでも良い
    command=referee_pb2.Referee.STOP
)

# --- UDPソケットの準備 ---
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

# TTL (Time-To-Live) の設定 (任意だが推奨)
# 1 に設定すると、同一サブネット内のみに届く (ルーターを越えない)
ttl = struct.pack('b', 1)
sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)

print(f"Dummy sender started. Sending to {MULTICAST_GROUP}:{MULTICAST_PORT}")
print("Sending alternating FORCE_START and STOP commands every 3 seconds...")

try:
    while True:
        # 1. 通常状態を送信
        serialized_normal = ref_msg_normal.SerializeToString()
        sock.sendto(serialized_normal, (MULTICAST_GROUP, MULTICAST_PORT))
        print(f"Sent: Stage={ref_msg_normal.stage}, Command={ref_msg_normal.command}")

        time.sleep(3) # 3秒待機

        # 2. STOP状態を送信
        serialized_stop = ref_msg_stop.SerializeToString()
        sock.sendto(serialized_stop, (MULTICAST_GROUP, MULTICAST_PORT))
        print(f"Sent: Stage={ref_msg_stop.stage}, Command={ref_msg_stop.command}")

        time.sleep(3) # 3秒待機

except KeyboardInterrupt:
    print("\nKeyboard interrupt received. Stopping dummy sender...")
finally:
    sock.close()
    print("Dummy sender socket closed.")