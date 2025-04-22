import time
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Literal

# --- Type Aliases (型エイリアス) ---
Team = Literal["UNKNOWN", "YELLOW", "BLUE"]
Location = Optional[Dict[str, float]] # 例: {"x": 1.23, "y": -0.45}

# --- Data Classes ---
@dataclass
class GameEvent:
    """
    オーケストレーターから 'event' トピックで送信される、
    特定のゲームイベント発生を示す情報。
    """
    timestamp: float = field(default_factory=time.time) # イベント生成時のUnixタイムスタンプ
    event_type: str = ""                                # イベント識別子 (確定済みリスト参照)
    priority: int = 0                                   # イベント優先度 (config_priority.yaml参照)
    data: Dict[str, Any] = field(default_factory=dict)  # イベント関連データ (別途定義リスト参照)

    def to_json(self) -> str:
        try:
            return json.dumps(asdict(self), ensure_ascii=False)
        except TypeError as e:
            print(f"Error serializing GameEvent to JSON: {e}\nData: {self}")
            raise ValueError(f"Could not serialize GameEvent to JSON: {e}") from e
    @classmethod
    def from_json(cls, json_str: str) -> 'GameEvent':
        try:
            data_dict = json.loads(json_str)
            return cls(**data_dict)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"Error decoding GameEvent JSON: {e}\nJSON string: {json_str}")
            raise ValueError(f"Could not decode GameEvent from JSON: {e}") from e

@dataclass
class TeamState:
    """GameStateUpdate内で使用される、チームごとの現在の状態"""
    name: str = ""
    score: int = 0
    red_cards: int = 0
    yellow_cards: int = 0
    yellow_card_times_us: List[int] = field(default_factory=list) # 各YCの残り時間(μs)
    timeouts_left: int = 0
    timeout_time_left_us: int = 0 # チーム全体の残りタイムアウト時間(μs)
    goalkeeper_id: int = 0
    foul_count: Optional[int] = None # ファウルカウント (Protobufではoptional)
    max_allowed_bots: Optional[int] = None # 最大許容ロボット数 (Protobufではoptional)


@dataclass
class GameStateUpdate:
    """
    オーケストレーターから 'state' トピックで定期的に送信される、
    試合全体の現在の状態。
    """
    timestamp: float = field(default_factory=time.time) # 状態更新時のUnixタイムスタンプ
    stage: str = ""           # 現在の Referee.Stage Enum名
    command: str = ""         # 現在の Referee.Command Enum名
    stage_time_left_us: Optional[int] = None  # 現在のステージ残り時間 (μs)
    current_action_time_remaining_us: Optional[int] = None # 現在のアクション残り時間 (μs)
    team_yellow: TeamState = field(default_factory=TeamState) # 黄色チーム状態
    team_blue: TeamState = field(default_factory=TeamState)   # 青チーム状態
    status_message: str = "" # 観客向けメッセージ (Referee.status_message)


    def to_json(self) -> str:
        try:
            return json.dumps(asdict(self), ensure_ascii=False)
        except TypeError as e:
            print(f"Error serializing GameStateUpdate to JSON: {e}\nData: {self}")
            raise ValueError(f"Could not serialize GameStateUpdate to JSON: {e}") from e
    @classmethod
    def from_json(cls, json_str: str) -> 'GameStateUpdate':
        try:
            data_dict = json.loads(json_str)
            yellow_data = data_dict.get('team_yellow', {})
            blue_data = data_dict.get('team_blue', {})
            known_team_fields = TeamState.__annotations__.keys()
            yellow_args = {k: v for k, v in yellow_data.items() if k in known_team_fields}
            blue_args = {k: v for k, v in blue_data.items() if k in known_team_fields}
            data_dict['team_yellow'] = TeamState(**yellow_args)
            data_dict['team_blue'] = TeamState(**blue_args)
            known_state_fields = cls.__annotations__.keys()
            state_args = {k: v for k, v in data_dict.items() if k in known_state_fields}
            return cls(**state_args)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            print(f"Error decoding GameStateUpdate JSON: {e}\nJSON string: {json_str}")
            raise ValueError(f"Could not decode GameStateUpdate from JSON: {e}") from e

# --- 使用例 (テスト用) ---
if __name__ == '__main__':
    # GameEventのテスト
    ge = GameEvent(event_type="EVENT_GOAL_CONFIRMED_YELLOW", priority=10, data={"team": "YELLOW", "score_yellow": 1})
    ge_json = ge.to_json()
    print(f"GameEvent JSON: {ge_json}")
    try:
        ge_decoded = GameEvent.from_json(ge_json)
        print(f"Decoded GameEvent: {ge_decoded}")
        assert ge == ge_decoded
    except ValueError as e:
        print(e)

    print("-" * 20)

    # GameStateUpdateのテスト
    ys = TeamState(name="YellowTeam", score=1, red_cards=0, yellow_cards=1)
    bs = TeamState(name="BlueTeam", score=0, red_cards=1)
    gs = GameStateUpdate(stage="NORMAL_FIRST_HALF", command="STOP", team_yellow=ys, team_blue=bs)
    gs_json = gs.to_json()
    # print(f"GameStateUpdate JSON: {gs_json}")
    print(f"Content to decode: {repr(gs_json)}") # repr() で特殊文字も表示
    try:
        gs_decoded = GameStateUpdate.from_json(gs_json)
        print(f"Decoded GameStateUpdate: {gs_decoded}")
        assert gs == gs_decoded

        # 不完全なJSONからのデコードテスト (team_blue が辞書でない)
        invalid_gs_json = gs_json.replace('"team_blue": {', '"team_blue": "invalid",')
        print(f"Invalid GameStateUpdate JSON: {invalid_gs_json}")
        gs_invalid = GameStateUpdate.from_json(invalid_gs_json)
        print(f"Decoded from invalid (should fail or handle): {gs_invalid}") # ここでエラーになるはず

    except ValueError as e:
        print(f"Caught expected error: {e}")