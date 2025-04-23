# listener.py
import socket
import struct
import time
import queue
import threading
from typing import Optional

# --- Protobufの生成済みコードをインポート ---
# (実際のパスに合わせて修正してください)
try:
    from state import ssl_gc_referee_message_pb2 as referee_pb2
except ImportError:
    print("Error: Protobuf generated code not found.")
    print("Please generate Python code from .proto files using protoc.")
    print("Example: protoc -I=./proto --python_out=./ ./proto/api/referee.proto ... (and dependencies)")
    exit(1)
# --- ここまで ---


class EventListener(threading.Thread):
    def __init__(self,
                 output_queue: queue.Queue,
                 multicast_group: str = "224.5.23.1",
                 multicast_port: int = 10003,
                 interface_ip: Optional[str] = None): # WSL/Linuxローカルテスト用
        super().__init__(daemon=True) # メインスレッド終了時に一緒に終了
        self.output_queue = output_queue
        self.multicast_group = multicast_group
        self.multicast_port = multicast_port
        self.interface_ip = interface_ip if interface_ip else '0.0.0.0' # 指定なければANY
        self._stop_event = threading.Event()
        print(f"Listener initialized for {self.multicast_group}:{self.multicast_port} on interface {self.interface_ip}")

    def stop(self):
        self._stop_event.set()
        print("Listener stop requested.")

    def run(self):
        print("Listener thread started.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # --- ポートへのバインド ---
        # マルチキャストアドレスではなく、ローカルインターフェースにバインド
        try:
            sock.bind((self.interface_ip, self.multicast_port))
            print(f"Listener bound to {self.interface_ip}:{self.multicast_port}")
        except OSError as e:
            print(f"Error binding socket: {e}")
            print("Check if the port is already in use or if the interface IP is correct.")
            return # スレッド終了

        # --- マルチキャストグループへの参加 ---
        mreq = struct.pack("4sl", socket.inet_aton(self.multicast_group), socket.INADDR_ANY)
        # interface_ip を指定する場合 (WSLなどでは必要になることが多い)
        mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton(self.interface_ip)
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            print(f"Listener joined multicast group {self.multicast_group}")
        except OSError as e:
             # 特にWSL等で `interface_ip='0.0.0.0'` の場合に失敗することがある
             # その場合は ANY ('') で試すか、適切なローカルIPを指定する必要がある
            print(f"Error joining multicast group: {e}")
            print("If using WSL or specific network setups, you might need to explicitly set interface_ip.")
            # 代替策: 別のインターフェース指定方法を試す (環境依存)
            # try:
            #     mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton('0.0.0.0')
            #     sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            #     print(f"Listener joined multicast group {self.multicast_group} using 0.0.0.0 interface")
            # except OSError as e2:
            #     print(f"Also failed joining multicast group with 0.0.0.0 interface: {e2}")
            #     sock.close()
            #     return # スレッド終了
            sock.close()
            return


        # --- 受信ループ ---
        sock.settimeout(10.0) # タイムアウトを設定してstop()をチェック
        ref_message = referee_pb2.Referee() # 再利用して効率化

        while not self._stop_event.is_set():
            try:
                data, addr = sock.recvfrom(65535) # バッファサイズ
                # print(f"Received {len(data)} bytes from {addr}") # デバッグ用
                ref_message.ParseFromString(data)
                # print(f"Parsed Referee msg: stage={ref_message.stage}, command={ref_message.command}") # デバッグ用
                
                msg_copy = referee_pb2.Referee()
                msg_copy.CopyFrom(ref_message)
                
                # デコード成功したらキューに入れる (コピーを渡す方が安全かもしれないが、まずはそのまま)
                self.output_queue.put(msg_copy)

            except socket.timeout:
                # タイムアウトは正常、stop()をチェックするため
                continue
            except socket.error as e:
                print(f"Socket error in listener: {e}")
                time.sleep(1) # エラー時は少し待つ
            except Exception as e: # Protobufのパースエラーなども含む
                print(f"Error processing UDP packet: {e}")

        # --- 終了処理 ---
        print("Listener shutting down...")
        try:
            # マルチキャストグループからの離脱 (必須ではないことが多いが一応)
            # mreq = struct.pack("4sl", socket.inet_aton(self.multicast_group), socket.INADDR_ANY)
            # sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq)
            pass
        except OSError as e:
            print(f"Error leaving multicast group: {e}")
        finally:
            sock.close()
            print("Listener socket closed.")


if __name__ == '__main__':
    # テスト用: リスナーを起動して10秒待つ
    # 実際にはオーケストレーターと同じプロセスで起動する想定
    print("Starting listener test...")
    msg_queue = queue.Queue()
    # WSLの場合は `ip addr` コマンドなどで適切なイーサネットアダプタのIPを確認し指定する
    # 例: listener = EventListener(msg_queue, interface_ip='172.20.80.1')
    listener = EventListener(msg_queue)
    listener.start()

    try:
        start_time = time.time()
        while time.time() - start_time < 10:
             # キューの中身を確認（デバッグ用）
            try:
                msg = msg_queue.get(timeout=0.1)
                print(f"Main thread received from queue: Stage={msg.stage}, Command={msg.command}")
            except queue.Empty:
                pass
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Keyboard interrupt received.")
    finally:
        listener.stop()
        listener.join() # スレッド終了を待つ
        print("Listener test finished.")