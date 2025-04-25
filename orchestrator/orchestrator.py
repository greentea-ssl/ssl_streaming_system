# orchestrator.py (Revised based on design overview)
import queue
import threading
import time
import zmq
import json
import traceback
from typing import List, Optional, Set, Dict, Any, Callable
from enum import Enum, auto

from . import protobuf_event_handlers

# --- データモデルとProtobuf Enumをインポート ---
# (パスは実際の環境に合わせてください)
try:
    # data_models.py は common ディレクトリにあると仮定
    from common.data_models import GameEvent, Team, Location # Locationも使う可能性があるのでインポート
except ImportError:
    print("Error: common/data_models.py not found.")
    exit(1)

try:
    # Protobuf 生成コードは state ディレクトリにあると仮定
    from state import ssl_gc_referee_message_pb2 as referee_pb2
    # ProtobufのGameEvent定義もインポート (型ヒントや定数参照用)
    from state import ssl_gc_game_event_pb2 as game_event_pb2
    from state import ssl_gc_common_pb2 as common_pb2
except ImportError:
    print("Error: Protobuf generated code not found in 'state' directory.")
    exit(1)
# --- ここまで ---

class InternalGameState(Enum):
    UNKNOWN = auto()
    HALTED = auto()
    STOPPED = auto()
    RUNNING = auto()
    PREPARE_KICKOFF_YELLOW = auto()
    PREPARE_KICKOFF_BLUE = auto()
    PREPARE_PENALTY_YELLOW = auto()
    PREPARE_PENALTY_BLUE = auto()
    DIRECT_FREE_YELLOW = auto()
    DIRECT_FREE_BLUE = auto()
    # INDIRECT_FREE = auto() # 必要なら
    TIMEOUT = auto()
    BALL_PLACEMENT = auto()

class Orchestrator(threading.Thread):
    def __init__(self,
                 input_queue: queue.Queue,
                 zmq_publisher_uri: str = "tcp://*:5555"):
        super().__init__(daemon=True)
        self.input_queue = input_queue
        self.zmq_publisher_uri = zmq_publisher_uri
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)

        # --- 状態保持用属性 ---
        self.internal_game_state: InternalGameState = InternalGameState.UNKNOWN # 内部状態属性
        self.previous_ref_msg: Optional[referee_pb2.Referee] = None

        self.previous_ref_msg: Optional[referee_pb2.Referee] = None
        self.processed_game_event_ids: Set[int] = set() # 処理済みProtobuf GameEventタイムスタンプ

        # --- 設定ファイル関連 (将来実装) ---
        # self.event_priorities: Dict[str, int] = {}
        # self.state_update_interval_sec: float = 1.0

        # --- イベントタイプとハンドラーのマッピング辞書 (インポートした関数を参照) ---
        self.protobuf_event_handlers: Dict[int, Callable] = {
            game_event_pb2.GameEvent.Type.BALL_LEFT_FIELD_TOUCH_LINE: protobuf_event_handlers.handle_ball_left_touchline,
            game_event_pb2.GameEvent.Type.BALL_LEFT_FIELD_GOAL_LINE: protobuf_event_handlers.handle_ball_left_goalline,
            game_event_pb2.GameEvent.Type.GOAL: protobuf_event_handlers.handle_goal,
            game_event_pb2.GameEvent.Type.PLACEMENT_SUCCEEDED: protobuf_event_handlers.handle_placement_succeeded,
            game_event_pb2.GameEvent.Type.PLACEMENT_FAILED: protobuf_event_handlers.handle_placement_failed,
            game_event_pb2.GameEvent.Type.NO_PROGRESS_IN_GAME: protobuf_event_handlers.handle_no_progress_in_game,
            game_event_pb2.GameEvent.Type.AIMLESS_KICK: protobuf_event_handlers.handle_aimless_kick,
            game_event_pb2.GameEvent.Type.KEEPER_HELD_BALL: protobuf_event_handlers.handle_keeper_held_ball,
            game_event_pb2.GameEvent.Type.BOT_DRIBBLED_BALL_TOO_FAR: protobuf_event_handlers.handle_bot_dribbled_ball_too_far,
            game_event_pb2.GameEvent.Type.BOT_PUSHED_BOT: protobuf_event_handlers.handle_bot_pushed_bot,
            game_event_pb2.GameEvent.Type.BOT_KICKED_BALL_TOO_FAST: protobuf_event_handlers.handle_bot_kicked_ball_too_fast,
            game_event_pb2.GameEvent.Type.BOT_CRASH_UNIQUE: protobuf_event_handlers.handle_bot_crash_unique,
            game_event_pb2.GameEvent.Type.BOT_CRASH_DRAWN: protobuf_event_handlers.handle_bot_crash_drawn,
            game_event_pb2.GameEvent.Type.DEFENDER_TOO_CLOSE_TO_KICK_POINT: protobuf_event_handlers.handle_defender_too_close_to_kick_point,
            
            # --- TODO: 他のイベントEnum値と対応するハンドラー関数を追加 ---
            # game_event_pb2.GameEvent.Type.AIMLESS_KICK: protobuf_event_handlers.handle_aimless_kick,
            # game_event_pb2.GameEvent.Type.UNSPORTING_BEHAVIOR_MINOR: protobuf_event_handlers.handle_unsporting_behavior_minor, # タイプ 32 用
        }
        print(f"Orchestrator initialized with {len(self.protobuf_event_handlers)} Protobuf event handlers.")
        
        # --- スレッド制御 ---
        self._stop_event = threading.Event()
        print(f"Orchestrator initialized, publishing to {self.zmq_publisher_uri}")
        # self._load_config() # 将来的にここで設定読み込み

    # --- 設定読み込みメソッド (将来実装) ---
    # def _load_config(self):
    #     print("TODO: Load config_orchestrator.yaml and config_priority.yaml")
    #     # self.zmq_publisher_uri = ...
    #     # self.state_update_interval_sec = ...
    #     # self.event_priorities = ...

    # --- 優先度取得メソッド (将来実装) ---
    # def _get_priority(self, event_type: str) -> int:
    #     return self.event_priorities.get(event_type, 5) # デフォルト優先度 5
    def _get_priority(self, event_type: str) -> int:
        """ 優先度を取得する (将来実装) """
        return 5 # デフォルト優先度 5
    
    def _update_internal_game_state(self, current_ref_msg: referee_pb2.Referee):
        cmd = current_ref_msg.command
        new_state = self.internal_game_state # デフォルトは維持

        if cmd == referee_pb2.Referee.Command.HALT:
            new_state = InternalGameState.HALTED
        elif cmd == referee_pb2.Referee.Command.STOP:
            new_state = InternalGameState.STOPPED
        elif cmd == referee_pb2.Referee.Command.PREPARE_KICKOFF_YELLOW:
            new_state = InternalGameState.PREPARE_KICKOFF_YELLOW
        elif cmd == referee_pb2.Referee.Command.PREPARE_KICKOFF_BLUE:
            new_state = InternalGameState.PREPARE_KICKOFF_BLUE
        elif cmd == referee_pb2.Referee.Command.PREPARE_PENALTY_YELLOW:
            new_state = InternalGameState.PREPARE_PENALTY_YELLOW
        elif cmd == referee_pb2.Referee.Command.PREPARE_PENALTY_BLUE:
            new_state = InternalGameState.PREPARE_PENALTY_BLUE
        elif cmd == referee_pb2.Referee.Command.DIRECT_FREE_YELLOW:
            new_state = InternalGameState.DIRECT_FREE_YELLOW
        elif cmd == referee_pb2.Referee.Command.DIRECT_FREE_BLUE:
            new_state = InternalGameState.DIRECT_FREE_BLUE
        elif cmd == referee_pb2.Referee.Command.TIMEOUT_YELLOW:
            new_state = InternalGameState.TIMEOUT_YELLOW
        elif cmd == referee_pb2.Referee.Command.TIMEOUT_BLUE:
            new_state = InternalGameState.TIMEOUT_BLUE
        elif cmd == referee_pb2.Referee.Command.BALL_PLACEMENT_YELLOW:
            new_state = InternalGameState.BALL_PLACEMENT_YELLOW
        elif cmd == referee_pb2.Referee.Command.BALL_PLACEMENT_BLUE:
            new_state = InternalGameState.BALL_PLACEMENT_BLUE
        elif cmd == referee_pb2.Referee.Command.FORCE_START:
            new_state = InternalGameState.RUNNING
        elif cmd == referee_pb2.Referee.Command.NORMAL_START:
            # NORMAL_START 自体は RUNNING 状態への移行を示すことが多い
            # (ただし、具体的なイベント生成は _detect_status_changes で行う)
            new_state = InternalGameState.RUNNING

        if new_state != self.internal_game_state:
            print(f"Internal Game State changed to: {new_state.name}")
            self.internal_game_state = new_state
        # else:
            # print(f"Internal Game State remains: {self.internal_game_state.name}")
            # pass

    def _map_protobuf_event_to_game_event(self, proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Optional[GameEvent]:
        """ Protobuf GameEvent をシステムの GameEvent にマッピングする (辞書と外部ハンドラーを使用) """
        event_enum = proto_event.type
        handler = self.protobuf_event_handlers.get(event_enum) # 辞書からハンドラーを取得

        if handler:
            try:
                # ★ インポートしたハンドラー関数を呼び出す
                event_type_str, data = handler(proto_event, current_ref)

                # TODO: 優先度を設定ファイルから取得
                priority = 5 # 仮

                return GameEvent(event_type=event_type_str, priority=priority, data=data)
            except Exception as e:
                # ... (エラーハンドリング) ...
                print(f"Orchestrator: Error processing event {event_enum}: {e}")
                print("Traceback:")
                traceback.print_exc()
                print("-" * 20)

                return None
        else:
            # ... (ハンドラー未定義の場合) ...
            print(f"Orchestrator: No handler defined for event type {event_enum}")
            return None
    
    def _detect_status_changes(self, prev_ref_msg: Optional[referee_pb2.Referee], current_ref_msg: referee_pb2.Referee) -> List[GameEvent]:
        """Refereeメッセージの主要なステータス変化を検出し、GameEventリストを返す"""
        events = []
        if prev_ref_msg is None: # 最初のメッセージでは比較できない
            return events

        # --- Stage Change Detection ---
        if current_ref_msg.stage != prev_ref_msg.stage:
            stage_enum_val = current_ref_msg.stage
            try:
                 # Protobuf Enum の数値から Enum 名 (文字列) を取得
                stage_name = referee_pb2.Referee.Stage.Name(stage_enum_val)
                event_type_str = f"STAGE_{stage_name}" # 例: "STAGE_NORMAL_FIRST_HALF"
                print(f"Orchestrator: Detected Stage change to {event_type_str}")
                data = {}
                # stage_time_left_us があればdataに追加
                if current_ref_msg.HasField("stage_time_left"):
                     # Protobufのsint64はPythonのintに対応, マイクロ秒単位に変換されているか確認
                     # 仕様書では stage_time_left は sint64 (milliseconds) となっている可能性もあるので注意
                     # ここでは us 単位と仮定 (要確認)
                     data["stage_time_left_us"] = current_ref_msg.stage_time_left # 仮
                     # もしミリ秒なら data["stage_time_left_us"] = current_ref_msg.stage_time_left * 1000

                # priority = self._get_priority(event_type_str) # 将来
                priority = 5 # 仮
                events.append(GameEvent(event_type=event_type_str, priority=priority, data=data))
            except ValueError:
                print(f"Orchestrator: Unknown Stage enum value: {stage_enum_val}")


        # --- Command Change Detection ---
        if current_ref_msg.command != prev_ref_msg.command:
            command_enum_val = current_ref_msg.command
            command_name = referee_pb2.Referee.Command.Name(command_enum_val)
            current_internal_state = self.internal_game_state

            try:
                if command_enum_val == referee_pb2.Referee.Command.NORMAL_START:
                    prev_command_enum_val = prev_ref_msg.command
                    event_type_str = f"COMMAND_NORMAL_START" # デフォルト
                    data = {}
                    priority = self._get_priority(event_type_str) # デフォルト優先度
                    
                    if current_internal_state == InternalGameState.PREPARE_KICKOFF_YELLOW:
                        event_type_str = "COMMAND_KICKOFF_START_YELLOW"
                        data["team"] = "YELLOW"
                        priority = self._get_priority(event_type_str) # 専用優先度
                    elif current_internal_state == InternalGameState.PREPARE_KICKOFF_BLUE:
                        event_type_str = "COMMAND_KICKOFF_START_BLUE"
                        data["team"] = "BLUE"
                        priority = self._get_priority(event_type_str)
                    elif current_internal_state == InternalGameState.PREPARE_PENALTY_YELLOW:
                        event_type_str = "COMMAND_PENALTY_KICK_START_YELLOW"
                        data["team"] = "YELLOW"
                        priority = self._get_priority(event_type_str)
                    elif current_internal_state == InternalGameState.PREPARE_PENALTY_BLUE:
                        event_type_str = "COMMAND_PENALTY_KICK_START_BLUE"
                        data["team"] = "BLUE"
                        priority = self._get_priority(event_type_str)
                    # else:
                        # 上記以外からの NORMAL_START はそのまま COMMAND_NORMAL_START とする
                        # (またはログ出力など)

                    print(f"Orchestrator: Detected specific start command: {event_type_str}")
                    events.append(GameEvent(event_type=event_type_str, priority=priority, data=data))

                else:
                    # 特殊なコマンド (KICKOFF_PREPなど) はチーム名を付与する必要があるかもしれない
                    event_type_str = f"COMMAND_{command_name}" # 例: "COMMAND_STOP"

                    data = {}
                    # チーム情報が必要なコマンドか判定 (例: KICKOFF_PREP_YELLOW)
                    # (より洗練された方法: Command名で判定、または専用のデータ構造を使う)
                    if "YELLOW" in command_name:
                        data["team"] = "YELLOW"
                        # event_type_str も調整 (例: "COMMAND_KICKOFF_PREP_YELLOW")
                    elif "BLUE" in command_name:
                        data["team"] = "BLUE"
                        # event_type_str も調整

                    # current_action_time_remaining_us が必要なコマンドか判定
                    if current_ref_msg.HasField("current_action_time_remaining"):
                        data["current_action_time_remaining_us"] = current_ref_msg.current_action_time_remaining # 仮 (単位要確認)

                    # ボールプレースメント位置が必要なコマンドか判定
                    if "BALL_PLACEMENT" in command_name and current_ref_msg.HasField("designated_position"):
                        data["placement_pos"] = {
                            "x": current_ref_msg.designated_position.x,
                            "y": current_ref_msg.designated_position.y
                        }

                    # タイムアウト関連情報が必要なコマンドか判定
                    if "TIMEOUT" in command_name:
                        team_info = current_ref_msg.yellow if "YELLOW" in command_name else current_ref_msg.blue
                        data["timeouts_left"] = team_info.timeouts
                        data["timeout_time_left_us"] = team_info.timeout_time # 仮 (単位要確認)

                    print(f"Orchestrator: Detected Command change to {event_type_str} with data {data}")
                    priority = self._get_priority(event_type_str) # 将来
                    
                    events.append(GameEvent(event_type=event_type_str, priority=priority, data=data))
            except ValueError:
                 print(f"Orchestrator: Unknown Command enum value: {command_enum_val}")


        # --- TODO: Other Status Changes (e.g., Timeout taken based on TeamInfo diff) ---

        return events

    def _process_game_events_list(self, current_ref_msg: referee_pb2.Referee) -> List[GameEvent]:
        """Referee.game_events リストを処理し、新しいイベントに対応するGameEventリストを返す"""
        events = []
        if not current_ref_msg.game_events:
            return events

        for proto_event in current_ref_msg.game_events:
            # イベント識別子としてタイムスタンプを使用 (衝突の可能性はあるが簡易的)
            # より堅牢にするならハッシュ値など
            # event_id = proto_event.event_timestamp
            event_id = proto_event.created_timestamp
            if event_id not in self.processed_game_event_ids:
                self.processed_game_event_ids.add(event_id)
                # print(f"Processing new game_event: type={proto_event.type}, timestamp={event_id}") # デバッグ

                # マッピング処理
                game_event = self._map_protobuf_event_to_game_event(proto_event, current_ref_msg)

                if game_event:
                    game_event.timestamp = event_id / 1_000_000.0
                    events.append(game_event)

        return events

    def _publish_event(self, game_event: GameEvent):
         """GameEvent を ZeroMQ で Publish する"""
         try:
             json_payload = game_event.to_json()
             self.publisher.send_multipart([
                 b"event",  # トピック名 (bytes)
                 json_payload.encode('utf-8') # ペイロード (bytes)
             ])
             print(f"Orchestrator: Published event: {game_event.event_type}")
         except Exception as e:
             print(f"Orchestrator: Error publishing event {game_event.event_type}: {e}")

    def run(self):
        """メインループ"""
        print("Orchestrator thread started.")
        try:
            self.publisher.bind(self.zmq_publisher_uri)
            print(f"Orchestrator bound to {self.zmq_publisher_uri}")
        except zmq.ZMQError as e:
            print(f"Error binding ZeroMQ socket: {e}")
            return # スレッド終了

        # TODO: Start periodic state publisher timer here if implementing GameStateUpdate

        while not self._stop_event.is_set():
            try:
                ref_msg: referee_pb2.Referee = self.input_queue.get(timeout=1.0)
                # print(f"Orchestrator: Received Referee message: {ref_msg}") # デバッグ

                # --- イベント検出 ---
                detected_events: List[GameEvent] = []
                # 1. Refereeステータス変化の検出
                detected_events.extend(self._detect_status_changes(self.previous_ref_msg, ref_msg))
                # 2. Referee.game_events リストの処理
                detected_events.extend(self._process_game_events_list(ref_msg))

                # --- イベント送信 ---
                for game_event in detected_events:
                    self._publish_event(game_event)

                # --- 状態更新 ---
                self._update_internal_game_state(ref_msg)
                self.previous_ref_msg = ref_msg # 次の比較のために現在のメッセージを保持
                self.input_queue.task_done()

            except queue.Empty:
                # タイムアウトは正常、stop()をチェックするため
                continue
            except Exception as e:
                print(f"Orchestrator: Error type in main loop: {type(e)}") # ★ 例外の型を出力
                print(f"Orchestrator: Error message: {e}")               # ★ 例外メッセージ (内容は "event_timestamp" かもしれない)
                print("Traceback:")
                traceback.print_exc() # ★ 完全なトレースバックを出力
                print("-" * 20) # 区切り線
                # エラー発生時も可能な限り継続試行
                time.sleep(1)

        # --- 終了処理 ---
        print("Orchestrator shutting down...")
        self.publisher.close()
        self.context.term()
        print("Orchestrator ZeroMQ context terminated.")

    def stop(self):
        """スレッドを停止する"""
        self._stop_event.set()
        print("Orchestrator stop requested.")
