# 例 (protoファイルがprotoディレクトリにある場合)
mkdir proto
# .proto ファイルを proto/ ディレクトリに配置
protoc --python_out=. proto/*.proto
# 同じ階層に ssl_gc_referee_message_pb2.py などが生成される
# これらを proto/__init__.py などで管理するか、
# 各スクリプトで from proto import ... のように参照