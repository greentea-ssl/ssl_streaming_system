# ベースイメージを指定
FROM python:3.12-slim

# --- ビルド時に使用する Poetry のバージョンを指定 ---
ARG POETRY_VERSION=2.1.2

# Poetryのインストールと設定に必要な環境変数
# (PATHとPYTHONPATHは実行時にも必要なのでENVを使用)
ENV POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH" \
    PYTHONPATH="${PYTHONPATH}:/app/proto"

# Poetryのインストールに必要なパッケージとPoetry本体をインストール
# ARGで指定したバージョンをインストール時に使用する
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip
RUN echo "Installing Poetry version ${POETRY_VERSION}" \
    && curl -sSL https://install.python-poetry.org | python3 - --version ${POETRY_VERSION} \
    # インストールされたバージョンを確認 (任意)
    && poetry --version

# protobufをソースからインストール
# RUN curl -Lo protoc.zip "https://github.com/protocolbuffers/protobuf/releases/latest/download/protoc-30.2-linux-x86_64.zip" \
#     && unzip protoc.zip -d /usr/local/bin/ \
#     && rm protoc.zip \
#     && echo "Protoc installed successfully. Version: $(protoc --version)"
RUN apt-get install -y --no-install-recommends \
    protobuf-compiler \
    libprotobuf-dev \
    python3-protobuf \
    && echo "Protobuf installed successfully. Version: $(protoc --version)"

RUN apt-get remove -y --purge curl unzip \
    && apt-get autoremove -y --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && echo "Cleanup completed." \

# 作業ディレクトリを設定
WORKDIR /app

# Poetryの設定ファイルをコピー
COPY pyproject.toml poetry.lock* ./

# Poetryを使って依存関係をインストール
RUN poetry install --no-root --no-interaction --no-ansi

# アプリケーションコードと、protoディレクトリ全体をコピー
COPY orchestrator/ ./orchestrator/
COPY common/ ./common/
# COPY proto/ ./proto/

# protoディレクトリをコンパイルして、Pythonコードを生成
COPY ssl-game-controller/proto/ ./ssl-game-controller/proto/
RUN mkdir -p /app/proto \
    && protoc --proto_path=ssl-game-controller/proto/ --python_out=/app/proto/ --pyi_out=/app/proto/ ssl-game-controller/proto/*/*.proto


# コンテナ起動時に実行されるコマンド
CMD ["python", "-u", "-m","orchestrator", \
     "--orchestrator-config", "/app/config/config_orchestrator.yaml", \
     "--priority-config", "/app/config/config_priority.yaml"]