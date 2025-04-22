# dummy_sender.py
import socket
import time
import json
import random
# protoディレクトリのパスを適切に設定するか、PYTHONPATHに追加してください
from proto.state import ssl_gc_referee_message_pb2 as RefereeProto
from proto.state import ssl_gc_game_event_pb2 as GameEventProto # GameEvent定義も必要
from proto.state import ssl_gc_common_pb2 as CommonProto # Team定義など

# 送信先設定
MULTICAST_IP = "224.5.23.1"
PORT = 10003

# 送信ソケット作成
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
# TTLを設定 (マルチキャストパケットがローカルネットワーク外に出ないように)
# sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1) # 通常は1で十分

def create_referee_message(stage=None, command=None, yellow_score=0, blue_score=0, game_event=None):
    """簡単なRefereeメッセージを生成するヘルパー関数"""
    ref_msg = RefereeProto.Referee()
    ref_msg.packet_timestamp = int(time.time() * 1_000_000) # マイクロ秒タイムスタンプ

    if stage is not None: ref_msg.stage = stage
    if command is not None: ref_msg.command = command

    ref_msg.yellow.name = "DummyYellow"
    ref_msg.yellow.score = yellow_score
    ref_msg.yellow.timeouts = 4 # 仮
    ref_msg.yellow.timeout_time = 300 * 1_000_000 # 仮
    ref_msg.yellow.goalkeeper = 0 # 仮

    ref_msg.blue.name = "DummyBlue"
    ref_msg.blue.score = blue_score
    ref_msg.blue.timeouts = 4 # 仮
    ref_msg.blue.timeout_time = 300 * 1_000_000 # 仮
    ref_msg.blue.goalkeeper = 0 # 仮

    if game_event:
        # game_events は repeated GameEvent なのでリストに追加
        new_event = ref_msg.game_events.add()
        new_event.CopyFrom(game_event) # GameEventオブジェクトをコピー

    # 必要に応じて他のフィールドも設定
    # ref_msg.stage_time_left = ...
    # ref_msg.command_counter = ...
    # ref_msg.command_timestamp = ...

    return ref_msg

def create_goal_event(team: CommonProto.Team):
    """簡単なGoalイベントを生成"""
    event = GameEventProto.GameEvent()
    event.type = GameEventProto.GameEvent.Type.GOAL
    event.created_timestamp = int(time.time() * 1_000_000)
    goal_details = event.goal # oneofフィールドにアクセス
    goal_details.by_team = team
    goal_details.kicking_team = team # 仮 (オウンゴールではない)
    goal_details.kicking_bot = random.randint(0, 10)
    # location等も設定可能
    return event

def send_message(message: RefereeProto.Referee):
    """RefereeメッセージをUDPマルチキャストで送信"""
    try:
        data = message.SerializeToString()
        sock.sendto(data, (MULTICAST_IP, PORT))
        print(f"Sent message: Stage={message.Stage.Name(message.stage)}, Command={message.Command.Name(message.command)}, Score={message.yellow.score}-{message.blue.score}, Events={len(message.game_events)}")
    except Exception as e:
        print(f"Error sending message: {e}")

if __name__ == "__main__":
    print("Starting Dummy SSL Event Sender...")
    print(f"Target: {MULTICAST_IP}:{PORT}")
    print("Commands: stop, halftime, goal_y, goal_b, quit")

    current_stage = RefereeProto.Referee.Stage.NORMAL_FIRST_HALF
    current_command = RefereeProto.Referee.Command.NORMAL_START
    yellow_score = 0
    blue_score = 0

    while True:
        try:
            cmd = input("> ").strip().lower()
            game_event_to_send = None

            if cmd == "stop":
                current_command = RefereeProto.Referee.Command.STOP
            elif cmd == "halftime":
                current_stage = RefereeProto.Referee.Stage.NORMAL_HALF_TIME
                current_command = RefereeProto.Referee.Command.HALT # ハーフタイムはHalt? Stop?
            elif cmd == "goal_y":
                yellow_score += 1
                game_event_to_send = create_goal_event(CommonProto.Team.YELLOW)
                # ゴール後は通常 STOP -> KICKOFF_PREP -> KICKOFF_START と遷移するが、ダミーでは省略
                current_command = RefereeProto.Referee.Command.STOP # 仮
            elif cmd == "goal_b":
                blue_score += 1
                game_event_to_send = create_goal_event(CommonProto.Team.BLUE)
                current_command = RefereeProto.Referee.Command.STOP # 仮
            elif cmd == "quit":
                break
            else:
                print("Unknown command.")
                continue

            msg = create_referee_message(
                stage=current_stage,
                command=current_command,
                yellow_score=yellow_score,
                blue_score=blue_score,
                game_event=game_event_to_send
            )
            send_message(msg)
            time.sleep(0.1) # 少し待つ

        except KeyboardInterrupt:
            break
        except EOFError: # input()がEOFを受け取った場合（リダイレクトなど）
             break

    print("Stopping Dummy Sender.")
    sock.close()