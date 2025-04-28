#!/bin/bash
# start_viz.sh - 可視化サービスを起動するスクリプト

# エラー時に終了
set -e

echo "===== サッカーフィールド可視化システムを起動しています ====="

# ZeroMQ WebSocketブリッジを起動（バックグラウンド）
echo "ZeroMQ-WebSocketブリッジを起動..."
python zmq_websocket_bridge.py &
BRIDGE_PID=$!

# HTTPサーバーを起動（バックグラウンド）
echo "HTTPサーバーを起動..."
python serve.py &
SERVER_PID=$!

echo "システムが起動しました！"
echo " - WebSocketブリッジは ws://localhost:8765 で利用可能"
echo " - Webインターフェースは http://localhost:8080 で利用可能"

# 終了時のクリーンアップ関数
function cleanup {
    echo "サービスを停止しています..."
    kill $BRIDGE_PID
    kill $SERVER_PID
    echo "サービスが停止しました"
    exit 0
}

# SIGTERM（Docker停止時）とSIGINT（Ctrl+C）をキャッチしてクリーンアップ
trap cleanup SIGTERM SIGINT

# コンテナが実行されている間待機
echo "コンテナが実行中です。ログを確認してください..."
wait