# orchestrator_app/protobuf_event_handlers.py

from typing import Dict, Any, Tuple, Optional

# --- 必要な Protobuf モジュールや共通定義、データモデルをインポート ---
# (パスは実際のプロジェクト構造に合わせてください)
try:
    # Protobuf 生成コードは state ディレクトリにあると仮定
    from state import ssl_gc_game_event_pb2 as game_event_pb2
    from state import ssl_gc_common_pb2 as common_pb2
    from state import ssl_gc_referee_message_pb2 as referee_pb2
except ImportError as e:
    print(f"Error importing protobuf modules in handlers: {e}")
    # 適切なエラー処理 (実行継続が難しい場合は exit など)
    exit(1)

try:
    # データモデルは common パッケージにあると仮定
    from common.data_models import Team, Location # 型エイリアスを使用
except ImportError as e:
    print(f"Error importing data_models: {e}")
    exit(1)
# --- ここまで ---


def _map_team_enum_to_str(team_enum: int) -> Team:
    """ProtobufのチームEnum値を文字列(Team型エイリアス)に変換"""
    if team_enum == common_pb2.YELLOW:
        return "YELLOW"
    elif team_enum == common_pb2.BLUE:
        return "BLUE"
    else:
        return "UNKNOWN"

def _extract_location(proto_event: game_event_pb2.GameEvent) -> Location:
    """Protobuf GameEvent から Location 辞書を抽出 (存在すれば)"""
    if proto_event.HasField("location"):
        return {"x": proto_event.location.x, "y": proto_event.location.y}
    return None

# === ハンドラー関数の実装 ===

def handle_ball_left_touchline(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """BALL_LEFT_FIELD_TOUCH_LINE イベントを処理"""
    specific_event = proto_event.ball_left_field_touch_line
    by_team_str = _map_team_enum_to_str(specific_event.by_team)
    event_type = f"EVENT_BALL_LEFT_TOUCHLINE_{by_team_str}"
    data = {
        "team": by_team_str,
        "last_touch_bot": specific_event.by_bot if specific_event.HasField("by_bot") else None,
        "location": _extract_location(specific_event)
    }
    print(f"Handler generated: {event_type} with data {data}") # デバッグ用ログ
    return event_type, data

def handle_ball_left_goalline(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """BALL_LEFT_FIELD_GOAL_LINE イベントを処理"""
    specific_event = proto_event.ball_left_field_goal_line # 同じサブメッセージを使用
    by_team_str = _map_team_enum_to_str(specific_event.by_team)
    event_type = f"EVENT_BALL_LEFT_GOALLINE_{by_team_str}"
    data = {
        "team": by_team_str,
        "last_touch_bot": specific_event.by_bot if specific_event.HasField("by_bot") else None,
        "location": _extract_location(specific_event)
    }
    print(f"Handler generated: {event_type} with data {data}") # デバッグ用ログ
    return event_type, data

def handle_goal(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """GOAL イベントを処理"""
    specific_event = proto_event.goal
    scoring_team_str = _map_team_enum_to_str(specific_event.by_team)
    event_type = f"EVENT_GOAL_CONFIRMED_{scoring_team_str}"
    data = {
        "team": scoring_team_str, # ゴールを決めたチーム
        "kicking_team": _map_team_enum_to_str(specific_event.kicking_team) if specific_event.HasField("kicking_team") else None,
        "kicking_bot": specific_event.kicking_bot if specific_event.HasField("kicking_bot") else None,
        "score_yellow": current_ref.yellow.score, # 最新のスコアを Referee メッセージから取得
        "score_blue": current_ref.blue.score,   # 最新のスコアを Referee メッセージから取得
        "location": _extract_location(proto_event), # イベント発生位置 (ボールの位置)
        # 必要であればゴール時のボール詳細位置も追加
        # "goal_location": {"x": specific_event.location.x, "y": specific_event.location.y} if specific_event.HasField("location") else None
    }
    print(f"Handler generated: {event_type} with data {data}") # デバッグ用ログ
    return event_type, data

# --- TODO: 他のイベントタイプに対応する handle_... 関数をここに追加 ---
# 例:
# def handle_aimless_kick(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
#    specific_event = proto_event.aimless_kick
#    ... (データ抽出ロジック) ...
#    return event_type, data

# def handle_unsporting_behavior_minor(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
#    # タイプ 32 のハンドラー
#    specific_event = proto_event.unsporting_behavior_minor
#    by_team_str = _map_team_enum_to_str(specific_event.by_team)
#    event_type = f"EVENT_UNSPORTING_BEHAVIOR_MINOR_{by_team_str}"
#    data = {
#        "team": by_team_str,
#        "reason": specific_event.reason if specific_event.HasField("reason") else None,
#        # 必要ならカード枚数などを current_ref から取得して追加
#        "current_yellow_cards": current_ref.yellow.yellow_cards if by_team_str == "YELLOW" else current_ref.blue.yellow_cards,
#    }
#    return event_type, data