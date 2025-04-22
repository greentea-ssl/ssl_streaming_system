# orchestrator.py
import zmq
import yaml
import time
import threading
import queue
from typing import Dict, List, Any, Optional

from common.data_models import GameEvent, GameStateUpdate, TeamState # 共通データ構造
# protoディレクトリのパスを適切に設定するか、PYTHONPATHに追加してください
from proto.state import ssl_gc_referee_message_pb2 as RefereeProto # エイリアス

class GameStateManager:
    """現在の試合状態とイベント検出に必要な情報を管理するクラス"""
    def __init__(self):
        self.current_stage: Optional[RefereeProto.Referee.Stage] = None
        self.current_command: Optional[RefereeProto.Referee.Command] = None
        self.previous_command: Optional[RefereeProto.Referee.Command] = None
        self.current_team_info: Dict[str, RefereeProto.Referee.TeamInfo] = {
            "YELLOW": RefereeProto.Referee.TeamInfo(),
            "BLUE": RefereeProto.Referee.TeamInfo()
        }
        self.processed_game_event_ids = set() # or use timestamps
        self.last_state_update = GameStateUpdate() # 最新の状態を保持

    def update_state(self, ref_msg: RefereeProto.Referee):
        """内部状態を最新のRefereeメッセージで更新"""
        self.previous_command = self.current_command
        self.current_stage = ref_msg.stage
        self.current_command = ref_msg.command
        self.current_team_info["YELLOW"] = ref_msg.yellow
        self.current_team_info["BLUE"] = ref_msg.blue
        # GameStateUpdateオブジェクトも更新
        self._update_last_state_update(ref_msg)

    def _update_last_state_update(self, ref_msg: RefereeProto.Referee):
        """保持しているGameStateUpdateオブジェクトを更新"""
        self.last_state_update.timestamp = time.time()
        self.last_state_update.stage = RefereeProto.Referee.Stage.Name(ref_msg.stage)
        self.last_state_update.command = RefereeProto.Referee.Command.Name(ref_msg.command)
        self.last_state_update.stage_time_left_us = ref_msg.stage_time_left if ref_msg.HasField("stage_time_left") else None
        self.last_state_update.current_action_time_remaining_us = ref_msg.current_action_time_remaining if ref_msg.HasField("current_action_time_remaining") else None
        self.last_state_update.status_message = ref_msg.status_message if ref_msg.HasField("status_message") else ""
        self._update_team_state(self.last_state_update.team_yellow, ref_msg.yellow)
        self._update_team_state(self.last_state_update.team_blue, ref_msg.blue)

    def _update_team_state(self, team_state_obj: TeamState, team_info_proto: RefereeProto.Referee.TeamInfo):
        """TeamStateオブジェクトをTeamInfo Protobufで更新"""
        team_state_obj.name = team_info_proto.name
        team_state_obj.score = team_info_proto.score
        team_state_obj.red_cards = team_info_proto.red_cards
        team_state_obj.yellow_cards = team_info_proto.yellow_cards
        team_state_obj.yellow_card_times_us = list(team_info_proto.yellow_card_times)
        team_state_obj.timeouts_left = team_info_proto.timeouts
        team_state_obj.timeout_time_left_us = team_info_proto.timeout_time
        team_state_obj.goalkeeper_id = team_info_proto.goalkeeper
        team_state_obj.foul_count = team_info_proto.foul_counter if team_info_proto.HasField("foul_counter") else None
        team_state_obj.max_allowed_bots = team_info_proto.max_allowed_bots if team_info_proto.HasField("max_allowed_bots") else None

    def detect_events(self, ref_msg: RefereeProto.Referee, prev_ref_msg: Optional[RefereeProto.Referee]) -> List[GameEvent]:
        """Refereeメッセージと内部状態を比較してGameEventリストを生成 (プロトタイプ版)"""
        events = []
        if not prev_ref_msg: # 初回メッセージ
             print("First message received, skipping event detection.")
             return events

        # --- プロトタイプ用: 簡単なイベント検出 ---
        # 1. COMMAND_STOP 検出
        if ref_msg.command == RefereeProto.Referee.Command.STOP and prev_ref_msg.command != RefereeProto.Referee.Command.STOP:
             print("Detected COMMAND_STOP")
             events.append(GameEvent(event_type="COMMAND_STOP", priority=4)) # 優先度は仮

        # 2. STAGE_HALF_TIME 検出
        if ref_msg.stage == RefereeProto.Referee.Stage.NORMAL_HALF_TIME and prev_ref_msg.stage != RefereeProto.Referee.Stage.NORMAL_HALF_TIME:
            print("Detected STAGE_HALF_TIME")
            events.append(GameEvent(event_type="STAGE_HALF_TIME", priority=5)) # 優先度は仮

        # 3. EVENT_GOAL_CONFIRMED_YELLOW 検出
        for game_event_proto in ref_msg.game_events:
             # 簡単のためID等での差分検出は省略し、毎回チェックする (プロトタイプ)
             if game_event_proto.type == RefereeProto.GameEvent.Type.GOAL:
                 goal_details = game_event_proto.goal # oneofフィールドから詳細取得
                 if goal_details.by_team == RefereeProto.Team.YELLOW:
                     print("Detected EVENT_GOAL_CONFIRMED_YELLOW")
                     # dataに必要な情報を詰める (スコアはTeamInfoから)
                     goal_data = {
                         "team": "YELLOW",
                         "kicking_team": RefereeProto.Team.Name(goal_details.kicking_team) if goal_details.HasField("kicking_team") else None,
                         "kicking_bot": goal_details.kicking_bot if goal_details.HasField("kicking_bot") else None,
                         "score_yellow": ref_msg.yellow.score,
                         "score_blue": ref_msg.blue.score
                         # location等も必要なら追加
                     }
                     events.append(GameEvent(event_type="EVENT_GOAL_CONFIRMED_YELLOW", priority=10, data=goal_data))
                 # else if goal_details.by_team == RefereeProto.Team.BLUE: ... (Blueも同様)

        # TODO: 他のイベント検出ロジックを追加 (Stage変更, Command変更, GameEvent差分, TeamInfo変化)
        # TODO: priority は config_priority.yaml から取得するようにする
        # TODO: data の内容をFIXした定義リストに合わせて充実させる

        return events

class ZmqPublisher:
    """ZeroMQ Publisherを管理するクラス"""
    def __init__(self, uri: str):
        self.uri = uri
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        try:
            print(f"Binding ZeroMQ PUB socket to {self.uri}")
            self.socket.bind(self.uri)
            print("ZeroMQ PUB socket bound successfully.")
        except zmq.ZMQError as e:
            print(f"Error binding ZeroMQ socket: {e}")
            self.context.term()
            raise # 初期化失敗は致命的

    def send(self, topic: str, message_obj: Any):
        """指定されたトピックでメッセージオブジェクトをJSON化して送信"""
        try:
            json_string = message_obj.to_json()
            # print(f"Publishing to topic '{topic}': {json_string}") # デバッグ用
            self.socket.send_multipart([topic.encode('utf-8'), json_string.encode('utf-8')])
        except Exception as e:
            print(f"Error sending message via ZeroMQ: {e}")

    def close(self):
        print("Closing ZeroMQ socket and context.")
        self.socket.close()
        self.context.term()

class Orchestrator:
    def __init__(self, listener_queue: queue.Queue, config_orchestrator_path: str, config_priority_path: str):
        self.listener_queue = listener_queue
        self.config_orchestrator_path = config_orchestrator_path
        self.config_priority_path = config_priority_path
        self.config_orchestrator = {}
        self.event_priorities = {}
        self.state_manager = GameStateManager()
        self.zmq_publisher = None
        self._stop_event = threading.Event()
        self._state_publish_thread = None
        self.previous_referee_message = None # イベント検出用に保持
        print("Orchestrator initialized.")

    def load_config(self):
        """設定ファイルを読み込む"""
        try:
            with open(self.config_orchestrator_path, 'r') as f:
                self.config_orchestrator = yaml.safe_load(f)
            print(f"Loaded orchestrator config: {self.config_orchestrator}")
            # 必須キーのチェック
            if 'zmq_publisher_uri' not in self.config_orchestrator or \
               'state_update_interval_sec' not in self.config_orchestrator:
                raise ValueError("Missing required keys in orchestrator config")

            with open(self.config_priority_path, 'r') as f:
                config_priority = yaml.safe_load(f)
                self.event_priorities = config_priority.get('event_priorities', {})
            print(f"Loaded {len(self.event_priorities)} event priorities.")
            return True
        except FileNotFoundError as e:
            print(f"Error loading config file: {e}")
            return False
        except (yaml.YAMLError, ValueError) as e:
            print(f"Error parsing config file: {e}")
            return False

    def setup(self):
        """初期化処理"""
        if not self.load_config():
            return False
        try:
            self.zmq_publisher = ZmqPublisher(self.config_orchestrator['zmq_publisher_uri'])
            return True
        except Exception as e:
            print(f"Orchestrator setup failed: {e}")
            return False

    def _publish_state_periodically(self):
        """GameStateUpdateを定期的にPublishするループ (別スレッドで実行)"""
        interval = self.config_orchestrator.get('state_update_interval_sec', 1.0)
        print(f"Starting periodic state publishing every {interval} seconds.")
        while not self._stop_event.wait(interval): # interval秒待つかstopされるまで
            if self.zmq_publisher:
                 # state_managerが保持する最新の状態を送る
                 # print(f"Publishing GameStateUpdate: {self.state_manager.last_state_update}") # デバッグ用
                 self.zmq_publisher.send("state", self.state_manager.last_state_update)
        print("Periodic state publishing stopped.")

    def run(self):
        """メインループ"""
        if not self.setup():
            print("Orchestrator failed to initialize. Exiting.")
            return

        # 定期送信スレッドを開始
        self._state_publish_thread = threading.Thread(target=self._publish_state_periodically, daemon=True)
        self._state_publish_thread.start()

        print("Orchestrator: Starting main loop...")
        while not self._stop_event.is_set():
            try:
                # キューからRefereeメッセージを取得 (タイムアウト付きで待つ)
                ref_msg = self.listener_queue.get(timeout=0.1)

                # 1. イベント検出 (プロトタイプ版)
                game_events: List[GameEvent] = self.state_manager.detect_events(ref_msg, self.previous_referee_message)

                # 2. GameEvent を Publish
                if self.zmq_publisher:
                    for event in game_events:
                        # TODO: 優先度をconfigから正しく設定する
                        # event.priority = self.event_priorities.get(event.event_type, 1)
                        self.zmq_publisher.send("event", event)

                # 3. 内部状態更新
                self.state_manager.update_state(ref_msg)
                self.previous_referee_message = ref_msg # 次の比較のために保存

                # 4. GameStateUpdate は定期送信スレッドが送信

                self.listener_queue.task_done() # キュー処理完了通知

            except queue.Empty:
                # タイムアウト、メッセージがない場合はループを続ける
                continue
            except Exception as e:
                print(f"Error in orchestrator main loop: {e}")
                # エラーによってはループを継続すべきか判断
                time.sleep(1)

        print("Orchestrator: Main loop stopped.")
        self.shutdown()

    def stop(self):
        print("Orchestrator: Stop requested.")
        self._stop_event.set()
        if self._state_publish_thread:
            self._state_publish_thread.join(timeout=2) # スレッド終了待ち

    def shutdown(self):
        if self.zmq_publisher:
            self.zmq_publisher.close()