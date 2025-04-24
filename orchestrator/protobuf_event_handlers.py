# orchestrator_app/protobuf_event_handlers.py

from typing import Dict, Any, Tuple, Optional

# --- 必要な Protobuf モジュールや共通定義、データモデルをインポート ---
# (パスは実際のプロジェクト構造に合わせてください)
try:
    # Protobuf 生成コードは state ディレクトリにあると仮定
    from state import ssl_gc_game_event_pb2 as game_event_pb2
    from state import ssl_gc_common_pb2 as common_pb2
    from state import ssl_gc_referee_message_pb2 as referee_pb2
    from geom import ssl_gc_geometry_pb2 as geometry_pb2
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
    try:
        if proto_event.HasField("location"):
            return {"x": proto_event.location.x, "y": proto_event.location.y}
        return None
    except ValueError as e:
        print(f"Error extracting location: {e}")
        return None
    
def _vector2_to_dict(proto_vector2: geometry_pb2.Vector2) -> Location:
    """ProtobufのVector2からLocation辞書を抽出 (Noneチェックは呼び出し元で行う)"""
    # Vector2 型は required な x, y を持つはず
    if proto_vector2 is not None and hasattr(proto_vector2, 'x') and hasattr(proto_vector2, 'y'):
        return {"x": proto_vector2.x, "y": proto_vector2.y}
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
        "location": _extract_location(specific_event), # イベント発生位置 (ボールの位置)
        # 必要であればゴール時のボール詳細位置も追加
        # "goal_location": {"x": specific_event.location.x, "y": specific_event.location.y} if specific_event.HasField("location") else None
    }
    print(f"Handler generated: {event_type} with data {data}") # デバッグ用ログ
    return event_type, data


def handle_placement_succeeded(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """PLACEMENT_SUCCEEDED イベントを処理"""
    # ssl_gc_game_event.proto の PlacementSucceeded メッセージ定義を参照
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    # GameEvent.event 内の oneof フィールド名は 'placement_succeeded' と仮定
    if proto_event.HasField("placement_succeeded"):
        specific_event = proto_event.placement_succeeded
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1;
        event_type_str = f"EVENT_PLACEMENT_SUCCEEDED_{team_str}"
        data["team"] = team_str
        # optional float time_taken = 2;
        if specific_event.HasField("time_taken"):
            data["time_taken"] = specific_event.time_taken
        # optional float precision = 3;
        if specific_event.HasField("precision"):
            data["precision"] = specific_event.precision
        # optional float distance = 4;
        if specific_event.HasField("distance"):
            data["distance"] = specific_event.distance
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        # このパスは通常通らないはず (typeとoneofフィールドは対応するため)
        print(f"Warning: PLACEMENT_SUCCEEDED event missing 'placement_succeeded' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing placement_succeeded data"}

    return event_type_str, data

def handle_placement_failed(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """PLACEMENT_FAILED イベントを処理"""
    # ssl_gc_game_event.proto の PlacementFailed メッセージ定義を参照
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    # GameEvent.event 内の oneof フィールド名は 'placement_failed' と仮定
    if proto_event.HasField("placement_failed"):
        specific_event = proto_event.placement_failed
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1;
        event_type_str = f"EVENT_PLACEMENT_FAILED_{team_str}"
        data["team"] = team_str
        # optional float remaining_dist = 2;
        if specific_event.HasField("remaining_dist"):
            data["remaining_distance"] = specific_event.remaining_dist
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: PLACEMENT_FAILED event missing 'placement_failed' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing placement_failed data"}

    return event_type_str, data

# === ファウル・ゲーム進行関連ハンドラーの実装 ===

def handle_no_progress_in_game(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """NO_PROGRESS_IN_GAME (Type 2) イベントを処理"""
    event_type_str = "EVENT_NO_PROGRESS" # チーム情報は含まれない
    data: Dict[str, Any] = {}
    # サブメッセージ名は 'no_progress_in_game' と仮定 (oneof フィールド)
    if proto_event.HasField("no_progress_in_game"):
        specific_event = proto_event.no_progress_in_game
        # optional float time = 1; (経過時間)
        if specific_event.HasField("time"):
            data["time"] = specific_event.time
    # このイベントには通常 location は含まれない（ssl_gc_game_event.proto 定義による）
    # もし必要なら current_ref のボール位置などを参照する？ (今回は含めない)
    print(f"Handler generated: {event_type_str} with data {data}")
    return event_type_str, data

def handle_aimless_kick(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """AIMLESS_KICK (Type 11) イベントを処理"""
    # サブメッセージ名は 'aimless_kick'
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    if proto_event.HasField("aimless_kick"):
        specific_event = proto_event.aimless_kick
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1;
        event_type_str = f"EVENT_AIMLESS_KICK_{team_str}"
        data["team"] = team_str
        # optional uint32 by_bot = 2;
        if specific_event.HasField("by_bot"):
            data["by_bot"] = specific_event.by_bot
        # optional Point location = 4; (.proto内ではlocationフィールドは無いが、GameEventのトップレベルにある場合)
        # ↑ .proto を確認すると AimlessKick メッセージ内に kick_location はあるが location はない
        # トップレベルの location を使う
        data["location"] = _extract_location(specific_event) # トップレベルの location を使用
        # optional Point kick_location = 3;
        if specific_event.HasField("kick_location"):
            data["kick_location"] = _extract_location(specific_event.kick_location)
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: AIMLESS_KICK event missing 'aimless_kick' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing aimless_kick data"}
    return event_type_str, data

def handle_keeper_held_ball(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """KEEPER_HELD_BALL (Type 22) イベントを処理"""
    # サブメッセージ名は 'keeper_held_ball'
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    if proto_event.HasField("keeper_held_ball"):
        specific_event = proto_event.keeper_held_ball
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1;
        event_type_str = f"EVENT_KEEPER_HELD_BALL_{team_str}"
        data["team"] = team_str
        # optional Point location = 2;
        if specific_event.HasField("location"):
            data["location"] = _extract_location(specific_event.location)
        # optional float duration = 3; (保持時間)
        if specific_event.HasField("duration"):
            data["duration"] = specific_event.duration
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: KEEPER_HELD_BALL event missing 'keeper_held_ball' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing keeper_held_ball data"}
    return event_type_str, data

def handle_bot_dribbled_ball_too_far(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """BOT_DRIBBLED_BALL_TOO_FAR (Type 23) イベントを処理 (再修正)"""
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    # oneof フィールド名は 'bot_dribbled_ball_too_far'
    if proto_event.HasField("bot_dribbled_ball_too_far"):
        specific_event = proto_event.bot_dribbled_ball_too_far
        team_str = _map_team_enum_to_str(specific_event.by_team)
        event_type_str = f"EVENT_EXCESSIVE_DRIBBLING_{team_str}"
        data["team"] = team_str
        if specific_event.HasField("by_bot"):
            data["by_bot"] = specific_event.by_bot
        if specific_event.HasField("start"):
            data["start"] = _vector2_to_dict(specific_event.start)
        if specific_event.HasField("end"):
            data["end"] = _vector2_to_dict(specific_event.end)
        # トップレベルの location を使用 (ドリブル超過が検出された位置)
        data["location"] = _extract_location(proto_event)
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: BOT_DRIBBLED_BALL_TOO_FAR missing sub-message: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing bot_dribbled_ball_too_far data"}
    return event_type_str, data

def handle_bot_pushed_bot(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """BOT_PUSHED_BOT (Type 24) イベントを処理"""
    # サブメッセージ名は 'bot_pushed_bot'
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    if proto_event.HasField("bot_pushed_bot"):
        specific_event = proto_event.bot_pushed_bot
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1; (違反したチーム)
        event_type_str = f"EVENT_BOT_PUSHING_{team_str}" # システムイベント名を調整
        data["team"] = team_str
        # optional uint32 violator = 2;
        if specific_event.HasField("violator"):
            data["violator"] = specific_event.violator
        # optional uint32 victim = 3;
        if specific_event.HasField("victim"):
            data["victim"] = specific_event.victim
        # optional float pushed_distance = 4;
        if specific_event.HasField("pushed_distance"):
            data["pushed_distance"] = specific_event.pushed_distance
        # optional Point location = 5;
        if specific_event.HasField("location"):
            data["location"] = _extract_location(specific_event.location)
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: BOT_PUSHED_BOT event missing 'bot_pushed_bot' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing bot_pushed_bot data"}
    return event_type_str, data

def handle_bot_kicked_ball_too_fast(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """BOT_KICKED_BALL_TOO_FAST (Type 28) イベントを処理"""
    # サブメッセージ名は 'bot_kicked_ball_too_fast'
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    if proto_event.HasField("bot_kicked_ball_too_fast"):
        specific_event = proto_event.bot_kicked_ball_too_fast
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1;
        event_type_str = f"EVENT_BALL_SPEED_TOO_FAST_{team_str}" # システムイベント名を調整
        data["team"] = team_str
        # optional uint32 by_bot = 2;
        if specific_event.HasField("by_bot"):
            data["by_bot"] = specific_event.by_bot
        # optional float initial_ball_speed = 3;
        if specific_event.HasField("initial_ball_speed"):
            data["initial_ball_speed"] = specific_event.initial_ball_speed
        # optional bool chipped = 4;
        if specific_event.HasField("chipped"):
            data["chipped"] = specific_event.chipped
        # optional Point location = 5;
        if specific_event.HasField("location"):
            data["location"] = _extract_location(specific_event.location)
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: BOT_KICKED_BALL_TOO_FAST event missing 'bot_kicked_ball_too_fast' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing bot_kicked_ball_too_fast data"}
    return event_type_str, data

def handle_bot_crash_unique(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """BOT_CRASH_UNIQUE (Type 29) イベントを処理"""
    # サブメッセージ名は 'bot_crash_unique'
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    if proto_event.HasField("bot_crash_unique"):
        specific_event = proto_event.bot_crash_unique
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1; (違反したチーム)
        event_type_str = f"EVENT_BOT_CRASH_UNIQUE_{team_str}"
        data["team"] = team_str
        # optional uint32 violator = 2;
        if specific_event.HasField("violator"):
            data["violator"] = specific_event.violator
        # optional uint32 victim = 3;
        if specific_event.HasField("victim"):
            data["victim"] = specific_event.victim
        # optional float crash_speed = 4;
        if specific_event.HasField("crash_speed"):
            data["crash_speed"] = specific_event.crash_speed
        # optional float speed_diff = 5;
        if specific_event.HasField("speed_diff"):
            data["speed_diff"] = specific_event.speed_diff
        # optional float crash_angle = 6;
        if specific_event.HasField("crash_angle"):
            data["crash_angle"] = specific_event.crash_angle
        # optional Point location = 7;
        if specific_event.HasField("location"):
            data["location"] = _extract_location(specific_event.location)
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: BOT_CRASH_UNIQUE event missing 'bot_crash_unique' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing bot_crash_unique data"}
    return event_type_str, data

def handle_bot_crash_drawn(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """BOT_CRASH_DRAWN (Type 30) イベントを処理"""
    # サブメッセージ名は 'bot_crash_drawn'
    event_type_str = "EVENT_BOT_CRASH_DRAWN" # チーム情報なし
    data: Dict[str, Any] = {}
    if proto_event.HasField("bot_crash_drawn"):
        specific_event = proto_event.bot_crash_drawn
        # optional uint32 bot_yellow = 1;
        if specific_event.HasField("bot_yellow"):
            data["bot_yellow"] = specific_event.bot_yellow
        # optional uint32 bot_blue = 2;
        if specific_event.HasField("bot_blue"):
            data["bot_blue"] = specific_event.bot_blue
        # optional float crash_speed = 3;
        if specific_event.HasField("crash_speed"):
            data["crash_speed"] = specific_event.crash_speed
        # optional float speed_diff = 4;
        if specific_event.HasField("speed_diff"):
            data["speed_diff"] = specific_event.speed_diff
        # optional float crash_angle = 5;
        if specific_event.HasField("crash_angle"):
            data["crash_angle"] = specific_event.crash_angle
        # optional Point location = 6;
        if specific_event.HasField("location"):
            data["location"] = _extract_location(specific_event.location)
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: BOT_CRASH_DRAWN event missing 'bot_crash_drawn' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing bot_crash_drawn data"}
    return event_type_str, data

def handle_defender_too_close_to_kick_point(proto_event: game_event_pb2.GameEvent, current_ref: referee_pb2.Referee) -> Tuple[str, Dict[str, Any]]:
    """DEFENDER_TOO_CLOSE_TO_KICK_POINT (Type 31) イベントを処理"""
    # サブメッセージ名は 'defender_too_close_to_kick_point'
    event_type_str = "UNKNOWN_PROTO_EVENT"
    data: Dict[str, Any] = {}
    if proto_event.HasField("defender_too_close_to_kick_point"):
        specific_event = proto_event.defender_too_close_to_kick_point
        team_str = _map_team_enum_to_str(specific_event.by_team) # required Team by_team = 1; (違反したチーム)
        event_type_str = f"EVENT_DEFENDER_TOO_CLOSE_{team_str}" # システムイベント名を調整
        data["team"] = team_str
        # optional uint32 by_bot = 2;
        if specific_event.HasField("by_bot"):
            data["by_bot"] = specific_event.by_bot
        # optional float distance = 3;
        if specific_event.HasField("distance"):
            data["distance"] = specific_event.distance
        # optional Point location = 4;
        if specific_event.HasField("location"):
            data["location"] = _extract_location(specific_event.location)
        print(f"Handler generated: {event_type_str} with data {data}")
    else:
        print(f"Warning: DEFENDER_TOO_CLOSE_TO_KICK_POINT event missing 'defender_too_close_to_kick_point' data: {proto_event}")
        return "EVENT_ERROR", {"reason": "Missing defender_too_close_to_kick_point data"}
    return event_type_str, data

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