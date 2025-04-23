# orchestrator_app/protobuf_event_handlers.py

from typing import Dict, Any, Tuple, Optional
# 必要な Protobuf モジュールや共通定義をインポート
from state import ssl_gc_game_event_pb2 as game_event_pb2
from state import ssl_gc_common_pb2 as common_pb2
from state import ssl_gc_referee_message_pb2 as referee_pb2
from common.data_models import Team, Location # common パッケージからインポート

def _map_team_enum_to_str(team_enum: int) -> Team:
    """(ここに _map_team_enum_to_str を移動または再定義)"""
    if team_enum == common_pb2.YELLOW: return "YELLOW"
    elif team_enum == common_pb2.BLUE: return "BLUE"
    else: return "UNKNOWN"

def handle_ball_left_touchline(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    specific_event = proto_event.ball_left_field
    by_team_str = _map_team_enum_to_str(specific_event.by_team)
    event_type = f"EVENT_BALL_LEFT_TOUCHLINE_{by_team_str}"
    data = {
        "team": by_team_str,
        "last_touch_bot": specific_event.by_bot if specific_event.HasField("by_bot") else None,
        "location": {"x": proto_event.location.x, "y": proto_event.location.y} if proto_event.HasField("location") else None
    }
    return event_type, data

def handle_ball_left_goalline(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    specific_event = proto_event.ball_left_field
    by_team_str = _map_team_enum_to_str(specific_event.by_team)
    event_type = f"EVENT_BALL_LEFT_GOALLINE_{by_team_str}"
    data = {
        "team": by_team_str,
        # ... (同様のデータ抽出) ...
    }
    return event_type, data

def handle_goal(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    specific_event = proto_event.goal
    scoring_team_str = _map_team_enum_to_str(specific_event.by_team)
    event_type = f"EVENT_GOAL_CONFIRMED_{scoring_team_str}"
    data = {
        "team": scoring_team_str,
        # ... (同様のデータ抽出、スコアは current_ref から) ...
         "score_yellow": current_ref.yellow.score,
         "score_blue": current_ref.blue.score,
    }
    return event_type, data

# --- TODO: 他のすべてのイベントタイプに対応する handle_... 関数をここに追加 ---
# def handle_aimless_kick(...): ...
# def handle_unsporting_behavior_minor(...): ... # タイプ 32 用
# ...