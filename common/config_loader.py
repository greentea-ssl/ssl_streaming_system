# 例: common/config_loader.py (または各アプリの utils.py など)
import yaml
import os
from typing import Dict, Any, Optional

def load_config(config_path: str) -> Optional[Dict[str, Any]]:
    """
    指定されたパスのYAMLファイルを読み込み、Python辞書として返す。
    エラー発生時は None を返す。
    """
    if not os.path.exists(config_path):
        print(f"Error: Config file not found at {config_path}")
        return None
    if not os.path.isfile(config_path):
        print(f"Error: Specified config path is not a file: {config_path}")
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) # 安全な safe_load を使用
        if not isinstance(config_data, dict):
            print(f"Error: Config file content is not a dictionary: {config_path}")
            return None
        print(f"Successfully loaded config from: {config_path}")
        return config_data
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {config_path}: {e}")
        return None
    except IOError as e:
        print(f"Error reading file {config_path}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error loading config {config_path}: {e}")
        return None