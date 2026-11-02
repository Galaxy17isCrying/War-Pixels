import json
import queue
import socket
import threading
import time


class MatchmakingClient:
    def __init__(self, host, port, request):
        self.host = host
        self.port = int(port)
        self.request = request
        self.player_id = request["profile"]["player_id"]
        self._incoming = queue.Queue()
        self._stop = threading.Event()
        self._input_lock = threading.Lock()
        self._latest_input = None
        self._socket = None
        self._thread = threading.Thread(target=self._run, name="overhead-ops-network", daemon=True)

    def start(self):
        self._thread.start()

    def send_input(self, action):
        with self._input_lock:
            self._latest_input = dict(action)

    def poll(self):
        messages = []
        while True:
            try:
                messages.append(self._incoming.get_nowait())
            except queue.Empty:
                return messages

    def close(self):
        self._stop.set()
        connection = self._socket
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=0.25)

    def _run(self):
        buffer = bytearray()
        try:
            with socket.create_connection((self.host, self.port), timeout=5.0) as connection:
                self._socket = connection
                connection.settimeout(0.05)
                self._send(connection, self.request)
                last_input_sent = 0.0
                while not self._stop.is_set():
                    now = time.monotonic()
                    if now - last_input_sent >= 0.05:
                        with self._input_lock:
                            action = self._latest_input
                        if action is not None:
                            self._send(connection, {"type": "input", "action": action})
                        last_input_sent = now
                    try:
                        data = connection.recv(65536)
                    except socket.timeout:
                        continue
                    if not data:
                        if not self._stop.is_set():
                            self._incoming.put({"type": "error", "message": "Server disconnected."})
                        break
                    buffer.extend(data)
                    if len(buffer) > 65536 and b"\n" not in buffer:
                        raise ValueError("Server message exceeded the 64 KiB limit.")
                    while b"\n" in buffer:
                        raw, _, remainder = buffer.partition(b"\n")
                        buffer = bytearray(remainder)
                        if len(raw) > 65536:
                            raise ValueError("Server message exceeded the 64 KiB limit.")
                        message = json.loads(raw.decode("utf-8"))
                        if not isinstance(message, dict):
                            raise ValueError("Server sent an invalid message.")
                        self._incoming.put(message)
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            if not self._stop.is_set():
                self._incoming.put({"type": "error", "message": str(exc)})
        finally:
            self._socket = None

    @staticmethod
    def _send(connection, message):
        encoded = json.dumps(message, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
        connection.sendall(encoded)
