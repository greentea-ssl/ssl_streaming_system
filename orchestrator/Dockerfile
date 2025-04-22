FROM python:3.12-slim

# 作業ディレクトリ設定
WORKDIR /app

# 依存関係ファイルをコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Protobuf生成コードをコピー (プロジェクトルートからの相対パス想定)
COPY proto ./proto
# 共通データモデルをコピー
COPY common/data_models.py ./common/

# オーケストレーターとリスナーのコードをコピー
COPY orchestrator/orchestrator.py .
COPY orchestrator/event_listener.py .

# 起動コマンド (main.py などでオーケストレーターを起動する想定)
# CMD ["python", "main_orchestrator.py"] # 仮
CMD ["tail", "-f", "/dev/null"]