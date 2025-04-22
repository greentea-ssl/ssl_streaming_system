# event_listener.py
import socket
import struct
import threading
import queue
from typing import Optional
import time

# protoディレクトリのパスを適切に設定するか、PYTHONPATHに追加してください
from proto.state import ssl_gc_referee_message_pb2 # 生成されたProtobuf Pythonコード

class EventListener(threading.Thread):
    def __init__(self, multicast_ip: str, port: int, output_queue: queue.Queue, interface_ip: Optional[str] = None, buffer_size: int = 65535):
        super().__init__(daemon=True) # メインスレッド終了時に自動終了
        self.multicast_ip = multicast_ip
        self.port = port
        self.output_queue = output_queue
        self.interface_ip = interface_ip
        self.buffer_size = buffer_size
        self.sock = None
        self._stop_event = threading.Event()
        print("EventListener initialized.")

    def setup_socket(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Windowsの場合は bind((interface_ip or "", self.port)) のようにする
            if hasattr(socket, "SO_REUSEPORT"):
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)

            # 特定インターフェースの指定 (Linuxの例)
            if self.interface_ip:
                 print(f"Binding to interface: {self.interface_ip}")
                 # self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.interface_ip)) # 送信インターフェース指定(通常不要)
                 self.sock.bind((self.interface_ip, self.port)) # 特定インターフェースで受信
            else:
                 print(f"Binding to all interfaces (0.0.0.0)")
                 self.sock.bind(("", self.port)) # すべてのインターフェースで受信

            # マルチキャストグループへの参加
            mreq = struct.pack("4sl", socket.inet_aton(self.multicast_ip), socket.INADDR_ANY)
            # もし interface_ip が指定されている場合、そちらを使う mreq の作り方もある
            # mreq = socket.inet_aton(self.multicast_ip) + socket.inet_aton(self.interface_ip)
            self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            print(f"UDP Socket setup complete. Listening on {self.multicast_ip}:{self.port}")
            return True
        except OSError as e:
            print(f"Error setting up socket: {e}")
            if self.sock:
                self.sock.close()
            self.sock = None
            return False
        except Exception as e:
            print(f"Unexpected error during socket setup: {e}")
            if self.sock:
                self.sock.close()
            self.sock = None
            return False


    def run(self):
        if not self.setup_socket():
            print("EventListener: Failed to setup socket. Thread exiting.")
            return

        print("EventListener: Starting receive loop...")
        while not self._stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(self.buffer_size)
                # print(f"Received {len(data)} bytes from {addr}") # デバッグ用
                referee_msg = ssl_gc_referee_message_pb2.Referee()
                try:
                    referee_msg.ParseFromString(data)
                    # パース成功したらキューに入れる
                    self.output_queue.put(referee_msg)
                    # print(f"Put Referee message to queue (Timestamp: {referee_msg.packet_timestamp})") # デバッグ用
                except Exception as e: # protobuf.message.DecodeError など
                    print(f"Error parsing Referee message: {e}")
            except socket.timeout: # recvfromでタイムアウトを設定した場合
                continue
            except OSError as e: # ソケットエラー (例: シャットダウン時)
                 if self._stop_event.is_set():
                     print("EventListener: Socket closed during shutdown.")
                     break
                 else:
                     print(f"Socket error in receive loop: {e}")
                     # 必要なら再接続ロジックなど
                     time.sleep(1) # 短い待機
            except Exception as e:
                print(f"Unexpected error in receive loop: {e}")
                time.sleep(1) # 短い待機

        print("EventListener: Receive loop stopped.")
        self.shutdown()

    def stop(self):
        print("EventListener: Stop requested.")
        self._stop_event.set()
        # ソケットを閉じてrecvfromのブロックを解除する
        if self.sock:
            self.sock.close()
            self.sock = None # クローズしたことを明確に

    def shutdown(self):
        if self.sock:
            try:
                self.sock.close()
                print("EventListener: Socket closed.")
            except Exception as e:
                print(f"Error closing socket: {e}")
            finally:
                self.sock = None