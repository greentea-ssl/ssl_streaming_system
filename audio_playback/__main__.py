import zmq
import json
import time
import threading
from typing import Optional, Dict, Any
import argparse
import os

from .audio_playback import AudioPlaybackModule

# --- データモデルをインポート ---
try:
    from common.data_models import GameEvent # 作成したデータモデル
    from common.config_loader import load_config # 設定ファイル読み込み関数
except ImportError:
    print("Error: data_models.py not found.")
    exit(1)

if __name__ == '__main__':
    # オーケストレーターが publish しているアドレスを指定
    # 同じマシンで動かすなら localhost でOK
    parser = argparse.ArgumentParser(...)
    parser.add_argument(
        '--config', 
        type=str,
        default='../config/config_audio.yaml', 
        help='Path to the config file')
    
    args = parser.parse_args()

    # パス解決
    script_dir = os.path.dirname(__file__)
    cfg_path = os.path.abspath(os.path.join(script_dir, args.config))

    # ★ 設定ファイルをここで読み込む
    audio_config_data = load_config(cfg_path)

    # 読み込み成功チェック
    if audio_config_data is None:
        print("Error: Failed to load configuration file. Exiting.")
        exit(1)
    print("Starting Audio Playback Module...")

    playback = AudioPlaybackModule(audio_config=audio_config_data)

    try:
        playback.run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Stopping playback module...")
    finally:
        playback.stop() # runループを止めるシグナル
        print("Playback Module finished.")