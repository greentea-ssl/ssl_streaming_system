# audio_playback.py
import zmq
import yaml
import time
import threading
import random
from queue import Queue, Full, Empty # 再生キュー用 (優先度付きも検討可)
from typing import List, Dict, Optional
import pathlib # pathlibを使う例
from common.data_models import GameEvent, GameStateUpdate # 共通データ構造
# from playsound import playsound # playsound3をインストールして使う想定
# 注意: playsound3 の正確なインポート名や Sound オブジェクトの仕様を確認する必要あり
try:
    # playsound3を想定
    from playsound3 import playsound, PlaysoundException, Sound
except ImportError:
    print("Warning: playsound3 library not found. Audio playback will be disabled.")
    # ダミー関数/クラスで置き換える
    def playsound(sound, block=False):
        print(f"[Dummy] Playing sound: {sound}")
        return None # ダミーのSoundオブジェクト相当
    class PlaysoundException(Exception): pass
    class Sound: # ダミー
        def stop(self): print("[Dummy] Stopping sound.")
        def is_alive(self): return False # ダミー


class PlaybackQueue:
    """再生待ちキュー（シンプルなFIFO、最大サイズ付き）"""
    def __init__(self, maxsize=2):
        self.queue = Queue(maxsize=maxsize)

    def put(self, event: GameEvent, file_path: str):
        try:
            # キューが満杯なら古いものを削除 (FIFO的な破棄)
            if self.queue.full():
                try:
                    self.queue.get_nowait()
                    print("PlaybackQueue: Queue was full, removed oldest item.")
                except Empty:
                    pass # ほぼ同時にput/getがあった場合
            self.queue.put_nowait((event, file_path))
            print(f"PlaybackQueue: Added event {event.event_type} (Pri: {event.priority})")
        except Full:
             print("PlaybackQueue: Queue is unexpectedly full after trying to make space.")
             pass # 満杯で追加できない場合

    def get(self) -> Optional[tuple[GameEvent, str]]:
        try:
            return self.queue.get_nowait()
        except Empty:
            return None

    def clear(self):
        print("PlaybackQueue: Clearing queue.")
        with self.queue.mutex:
            self.queue.queue.clear()

    def is_empty(self) -> bool:
        return self.queue.empty()

class AudioPlayer:
    """音声再生と状態管理を行うクラス"""
    def __init__(self):
        self.current_playback: Optional[tuple[GameEvent, Sound]] = None
        self._playback_thread: Optional[threading.Thread] = None
        self._stop_current_playback = threading.Event()

    def play(self, file_path: str, event: GameEvent, on_finish_callback):
        """非同期で音声ファイルを再生する"""
        if self.is_playing():
            print("AudioPlayer Error: Already playing.")
            return

        print(f"AudioPlayer: Starting playback for {event.event_type} (Pri: {event.priority}), File: {file_path}")
        self._stop_current_playback.clear()

        def playback_task():
            sound_object = None
            try:
                # playsoundを非同期(block=False)で実行
                # Soundオブジェクトを返すか、または例外を投げる
                sound_object = playsound(file_path, block=False)
                self.current_playback = (event, sound_object)

                # --- 再生完了待ち ---
                # playsound3がSoundオブジェクトを返すなら、それで完了を待てるか？
                # (ドキュメントや実際の動作確認が必要)
                # 代替案1: Soundオブジェクトがなければ時間ベースで待つ (不正確)
                # 代替案2: playsound(block=True)を別スレッドで実行し、スレッド終了を待つ
                # ここでは代替案2を想定した疑似コード
                if sound_object:
                     # is_alive的なメソッドがあれば使う (playsound3の仕様次第)
                     # while sound_object.is_alive() and not self._stop_current_playback.is_set():
                     #    time.sleep(0.1)
                     # 仮に block=True を別スレッドで動かす場合
                     def blocking_play():
                         try:
                             playsound(file_path, block=True)
                         except Exception as e:
                              print(f"Error during blocking playback: {e}")
                     
                     play_thread = threading.Thread(target=blocking_play)
                     play_thread.start()
                     while play_thread.is_alive() and not self._stop_current_playback.is_set():
                         time.sleep(0.1)
                     
                     if self._stop_current_playback.is_set():
                         print("AudioPlayer: Playback explicitly stopped.")
                         # playsound(block=True)を外部から停止できるか？ 難しい可能性
                     else:
                          print("AudioPlayer: Playback finished naturally.")

                else:
                     # Soundオブジェクトがない場合、仮に1秒待つ
                     print("AudioPlayer: Sound object not available, waiting 1 sec (dummy).")
                     time.sleep(1)

            except PlaysoundException as e:
                print(f"AudioPlayer Error: Failed to play {file_path}. Reason: {e}")
            except Exception as e:
                 print(f"AudioPlayer Error: Unexpected error during playback. Reason: {e}")
            finally:
                # 再生終了（自然終了 or stop呼び出し or エラー）
                self.current_playback = None
                print(f"AudioPlayer: Playback ended for event {event.event_type}.")
                on_finish_callback() # 再生完了を通知

        # 再生タスクを別スレッドで開始
        self._playback_thread = threading.Thread(target=playback_task, daemon=True)
        self._playback_thread.start()

    def stop(self):
        """現在の再生を停止する"""
        if self.is_playing() and self.current_playback:
            print("AudioPlayer: Stopping current playback...")
            self._stop_current_playback.set() # 再生待ちループを止めるフラグ
            sound_object = self.current_playback[1]
            if sound_object and hasattr(sound_object, 'stop'):
                try:
                    sound_object.stop() # playsound3 の stop() を試す
                    print("AudioPlayer: sound_object.stop() called.")
                except Exception as e:
                    print(f"AudioPlayer: Error calling sound_object.stop(): {e}")
            # block=Trueを別スレッドで動かした場合、そのスレッドを強制停止するのは難しい
            # 音声ライブラリによっては停止できない可能性あり

            # スレッドの終了を少し待つ
            if self._playback_thread:
                 self._playback_thread.join(timeout=0.5)
            self.current_playback = None # 停止したら再生中状態を解除


    def is_playing(self) -> bool:
        """現在再生中かどうか"""
        # スレッドが生きているかで判断するのが確実か？
        return self._playback_thread is not None and self._playback_thread.is_alive()
        # return self.current_playback is not None # 単純なフラグ管理

    def get_current_priority(self) -> int:
         """現在再生中のイベントの優先度を取得"""
         return self.current_playback[0].priority if self.is_playing() and self.current_playback else -1

class AudioPlaybackModule:
    def __init__(self, publisher_uri: str, config_audio_path: str):
        self.publisher_uri = publisher_uri
        self.config_audio_path = config_audio_path
        self.audio_config = {}
        self.event_actions = {}
        self.default_action = {"action": "ignore"}
        self.zmq_context = None
        self.subscriber_socket = None
        self.is_connected = False
        self.player = AudioPlayer()
        self.queue = PlaybackQueue(maxsize=2) # キューサイズを2に設定
        self._stop_event = threading.Event()
        self._receive_thread = None
        self._reconnect_thread = None
        print("AudioPlaybackModule initialized.")

    def load_config(self):
        """音声設定ファイルを読み込む"""
        try:
            with open(self.config_audio_path, 'r') as f:
                self.audio_config = yaml.safe_load(f)
            self.event_actions = self.audio_config.get('event_actions', {})
            self.default_action = self.audio_config.get('DEFAULT_ACTION', {'action': 'ignore'})
            print(f"Loaded audio config with {len(self.event_actions)} actions.")
            # TODO: ファイルパスの基準ディレクトリ解決
            # self.audio_base_dir = os.path.dirname(os.path.abspath(self.config_audio_path))
            return True
        except FileNotFoundError as e:
            print(f"Error loading audio config file: {e}")
            return False
        except yaml.YAMLError as e:
            print(f"Error parsing audio config file: {e}")
            return False

    def setup_zmq(self):
        """ZeroMQ Subscriberをセットアップ"""
        try:
            self.zmq_context = zmq.Context()
            self.subscriber_socket = self.zmq_context.socket(zmq.SUB)
            # 再接続設定 (オプション)
            self.subscriber_socket.setsockopt(zmq.RCVTIMEO, 1000) # 受信タイムアウト1秒
            # self.subscriber_socket.setsockopt(zmq.RECONNECT_IVL, 1000) # 再接続間隔1秒
            # self.subscriber_socket.setsockopt(zmq.RECONNECT_IVL_MAX, 5000) # 最大再接続間隔5秒
            print(f"Connecting ZeroMQ SUB socket to {self.publisher_uri}")
            self.subscriber_socket.connect(self.publisher_uri)
            # トピックを購読
            self.subscriber_socket.setsockopt_string(zmq.SUBSCRIBE, "event")
            # self.subscriber_socket.setsockopt_string(zmq.SUBSCRIBE, "state") # 必要なら購読
            print("ZeroMQ SUB socket connected and subscribed.")
            self.is_connected = True
            return True
        except zmq.ZMQError as e:
            print(f"Error setting up ZeroMQ SUB socket: {e}")
            if self.subscriber_socket: self.subscriber_socket.close()
            if self.zmq_context: self.zmq_context.term()
            self.is_connected = False
            return False

    def _receive_loop(self):
        """メッセージ受信ループ (別スレッドで実行)"""
        print("AudioPlaybackModule: Starting receive loop...")
        while not self._stop_event.is_set():
            if not self.is_connected:
                # 接続試行中に待機
                time.sleep(1)
                continue
            try:
                # マルチパートで受信 (トピック + メッセージ)
                topic_bytes, message_bytes = self.subscriber_socket.recv_multipart()
                topic = topic_bytes.decode('utf-8')
                message_json = message_bytes.decode('utf-8')
                # print(f"Received on topic '{topic}': {message_json}") # デバッグ用

                if topic == "event":
                    try:
                        game_event = GameEvent.from_json(message_json)
                        self.process_game_event(game_event)
                    except ValueError as e:
                        print(f"Error decoding GameEvent: {e}")
                elif topic == "state":
                     try:
                        state_update = GameStateUpdate.from_json(message_json)
                        # print(f"Received GameStateUpdate: Stage={state_update.stage}") # ログ出力等
                     except ValueError as e:
                         print(f"Error decoding GameStateUpdate: {e}")

            except zmq.Again:
                # 受信タイムアウト、メッセージなし
                continue
            except zmq.ZMQError as e:
                print(f"ZeroMQ error in receive loop: {e}. Attempting to reconnect...")
                self.is_connected = False
                # 再接続処理は別スレッドで行う
            except Exception as e:
                print(f"Unexpected error in receive loop: {e}")
                time.sleep(1)

        print("AudioPlaybackModule: Receive loop stopped.")

    def _reconnect_loop(self):
         """ZeroMQ再接続試行ループ (別スレッドで実行)"""
         print("AudioPlaybackModule: Starting reconnect loop...")
         while not self._stop_event.is_set():
             if not self.is_connected:
                 print("Attempting to reconnect ZeroMQ SUB socket...")
                 if self.subscriber_socket: self.subscriber_socket.close()
                 if self.zmq_context: self.zmq_context.term() # コンテキストも再作成
                 time.sleep(2) # 少し待ってから再試行
                 self.setup_zmq() # 再度セットアップを試みる
             time.sleep(5) # 5秒ごとに接続状態を確認・再試行
         print("AudioPlaybackModule: Reconnect loop stopped.")


    def process_game_event(self, event: GameEvent):
        """受信したGameEventを処理する"""
        print(f"Processing event: {event.event_type} (Pri: {event.priority})")
        action_config = self.event_actions.get(event.event_type, self.default_action)
        action = action_config.get("action", "ignore")

        if action == "ignore":
            print(f" Action for {event.event_type} is 'ignore'. Skipping.")
            return

        if action == "play_file":
            files_config = action_config.get("files")
            if not files_config or not isinstance(files_config, list):
                print(f" Error: 'files' list is missing or invalid for event {event.event_type}")
                return

            # ファイル選択ロジック (ランダム、weight考慮)
            selected_path = self._select_audio_file(files_config)
            if not selected_path:
                print(f" Error: Could not select a valid audio file for event {event.event_type}")
                return

            # 再生制御ロジック
            self.schedule_playback(selected_path, event)

    def _select_audio_file(self, files_config: List[Dict]) -> Optional[str]:
        """files設定リストから再生するファイルパスを選択 (weight考慮)"""
        # TODO: 相対パス解決 (self.audio_base_dir を基準に)
        base_dir = pathlib.Path(self.config_audio_path).parent / "sounds" # 仮

        valid_files = []
        weights = []
        total_weight = 0
        has_weight = False

        for file_info in files_config:
            path_str = file_info.get("path")
            if not path_str or not isinstance(path_str, str): continue

            # ここでパスを解決する
            # resolved_path = os.path.join(self.audio_base_dir, path_str)
            resolved_path = base_dir / path_str # pathlib を使う例

            # ファイル存在チェック (オプションだが推奨)
            if not resolved_path.is_file():
                 print(f" Warning: Audio file not found: {resolved_path}")
                 continue

            valid_files.append(str(resolved_path))
            weight = file_info.get("weight")
            if weight is not None and isinstance(weight, (int, float)) and weight > 0:
                weights.append(float(weight))
                total_weight += float(weight)
                has_weight = True
            else:
                weights.append(None) # 重み指定なし

        if not valid_files: return None
        if len(valid_files) == 1: return valid_files[0]

        # 選択ロジック
        if not has_weight: # 重み指定が全くない場合 -> 等確率
            return random.choice(valid_files)
        else:
            # 重みが指定されている場合
            final_weights = []
            num_unspecified = weights.count(None)
            weight_sum_specified = sum(w for w in weights if w is not None)

            # 正規化 or 残り確率分配
            if weight_sum_specified <= 0 and num_unspecified > 0: # 重み指定が無効で、未指定がある場合 -> 等確率
                 return random.choice(valid_files)

            # 各ファイルの重みを計算 (合計が1になるように正規化)
            # 簡単な正規化: 指定された重みの比率で選択
            normalized_weights = []
            for w in weights:
                 if w is not None:
                     normalized_weights.append(w)
                 else:
                      # 未指定の場合の扱い (例: 平均値を入れる、0にするなど)
                      # ここでは単純に比率計算のため0扱いとする (より良い方法は要検討)
                      normalized_weights.append(0)
            
            total_norm_weight = sum(normalized_weights)
            if total_norm_weight <= 0: # 万が一、有効な重みがなかった場合
                 return random.choice(valid_files)

            final_probabilities = [w / total_norm_weight for w in normalized_weights]
            
            # 重み付きランダム選択
            return random.choices(valid_files, weights=final_probabilities, k=1)[0]


    def schedule_playback(self, file_path: str, event: GameEvent):
        """優先度に基づき再生をスケジュールする"""
        current_priority = self.player.get_current_priority()

        if not self.player.is_playing():
            print(f"Scheduler: No playback running. Starting {event.event_type} (Pri: {event.priority})")
            self.player.play(file_path, event, self._handle_playback_finished)
        elif event.priority > current_priority:
            print(f"Scheduler: Interrupting current playback (Pri: {current_priority}) for {event.event_type} (Pri: {event.priority})")
            self.player.stop()
            self.queue.clear() # 割り込み時はキューもクリア
            # stop()が完了するのを少し待つか、すぐに次の再生を開始するか？
            # すぐに開始してみる
            self.player.play(file_path, event, self._handle_playback_finished)
        else:
            print(f"Scheduler: Queuing event {event.event_type} (Pri: {event.priority}) as current priority is {current_priority}")
            self.queue.put(event, file_path)

    def _handle_playback_finished(self):
        """再生完了時に呼び出されるコールバック"""
        print("Playback finished. Checking queue...")
        next_item = self.queue.get()
        if next_item:
            next_event, next_path = next_item
            print(f"Playing next item from queue: {next_event.event_type} (Pri: {next_event.priority})")
            self.player.play(next_path, next_event, self._handle_playback_finished)
        else:
            print("Playback queue is empty.")

    def start(self):
        """モジュールの処理を開始"""
        if not self.load_config():
            print("AudioPlaybackModule failed to load config. Exiting.")
            return
        if not self.setup_zmq():
             print("AudioPlaybackModule failed to setup ZeroMQ. Starting reconnect loop.")
             # 再接続スレッドを開始してバックグラウンドで試行させる
             self._reconnect_thread = threading.Thread(target=self._reconnect_loop, daemon=True)
             self._reconnect_thread.start()

        # 受信ループを別スレッドで開始
        self._receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._receive_thread.start()
        print("AudioPlaybackModule started.")

    def stop(self):
        """モジュールの処理を停止"""
        print("AudioPlaybackModule: Stop requested.")
        self._stop_event.set()
        if self._receive_thread:
            self._receive_thread.join(timeout=2)
        if self._reconnect_thread:
             self._reconnect_thread.join(timeout=1) # 再接続ループも止める
        self.player.stop() # 再生中の音声を停止
        self.queue.clear() # キューもクリア
        if self.subscriber_socket: self.subscriber_socket.close()
        if self.zmq_context: self.zmq_context.term()
        print("AudioPlaybackModule stopped.")