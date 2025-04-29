mkdir -p proto
# .proto ファイルを proto/ ディレクトリに配置
# protoc --python_out= proto/*.proto --pyi_out=
protoc --proto_path=ssl-game-controller/proto/ --python_out=./proto/ --pyi_out=./proto/ ssl-game-controller/proto/*/*.proto
