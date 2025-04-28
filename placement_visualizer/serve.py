#!/usr/bin/env python3
import http.server
import socketserver
import os
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("http_server")

# 環境変数から設定を読み込むか、デフォルト値を使用
PORT = int(os.environ.get('HTTP_PORT', 8080))
DIRECTORY = os.environ.get('SERVE_DIRECTORY')

# 作業ディレクトリを変更
os.chdir(DIRECTORY)
logger.info(f"Working directory set to: {os.getcwd()}")

class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)

# すべてのインターフェイスでリッスン
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    logger.info(f"Serving HTTP at http://0.0.0.0:{PORT}")
    httpd.serve_forever()