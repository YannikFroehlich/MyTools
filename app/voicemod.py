import base64
import hashlib
import json
import os
import socket
import struct
import time
import uuid


VOICEMOD_DEFAULT_PORTS = (
    59129,
    20000,
    39273,
    42152,
    43782,
    46667,
    35679,
    37170,
    38501,
    33952,
    30546,
)

WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


class VoicemodError(Exception):
    status_code = 502


class VoicemodConfigurationError(VoicemodError):
    status_code = 500


class VoicemodConnectionError(VoicemodError):
    status_code = 502


class VoicemodAuthorizationError(VoicemodError):
    status_code = 401


class VoicemodProtocolError(VoicemodError):
    status_code = 502


def parse_voicemod_ports(value):
    if not value:
        return list(VOICEMOD_DEFAULT_PORTS)

    ports = []

    for item in str(value).split(","):
        item = item.strip()
        if not item:
            continue

        try:
            port = int(item)
        except ValueError:
            continue

        if 0 < port <= 65535:
            ports.append(port)

    return ports or list(VOICEMOD_DEFAULT_PORTS)


def send_voicemod_action(api_key, action, payload=None, host="127.0.0.1", ports=None):
    api_key = (api_key or "").strip()
    action = (action or "").strip()
    payload = payload or {}
    ports = list(ports or VOICEMOD_DEFAULT_PORTS)

    if not api_key:
        raise VoicemodConfigurationError("VOICEMOD_API_KEY fehlt in der .env.")

    if not action:
        raise VoicemodConfigurationError("Keine Voicemod Aktion angegeben.")

    last_error = None

    for port in ports:
        client = _VoicemodWebSocket(host=host, port=port)

        try:
            client.connect()
            register_message = _register_client(client, api_key)
            messages = _send_action_and_collect_messages(client, action, payload)

            return {
                "port": port,
                "registered": True,
                "register": register_message,
                "messages": messages,
            }
        except VoicemodAuthorizationError:
            raise
        except (OSError, VoicemodProtocolError) as exc:
            last_error = exc
        finally:
            client.close()

    detail = f" Letzter Fehler: {last_error}" if last_error else ""
    raise VoicemodConnectionError(f"Voicemod ist lokal nicht erreichbar.{detail}")


def _register_client(client, api_key):
    client.send_json({
        "action": "registerClient",
        "id": _create_id(),
        "payload": {
            "clientKey": api_key,
        },
    })

    deadline = time.monotonic() + 2.5

    while time.monotonic() < deadline:
        message = client.recv_json()

        if message.get("action") != "registerClient":
            continue

        status = message.get("payload", {}).get("status", {})
        code = status.get("code")

        if code == 200:
            return message

        raise VoicemodAuthorizationError("Voicemod API-Key wurde nicht autorisiert.")

    raise VoicemodProtocolError("Voicemod hat die Autorisierung nicht bestaetigt.")


def _send_action_and_collect_messages(client, action, payload):
    client.send_json({
        "action": action,
        "id": _create_id(),
        "payload": payload,
    })

    messages = []
    deadline = time.monotonic() + 1.5

    while time.monotonic() < deadline and len(messages) < 6:
        try:
            message = client.recv_json()
        except socket.timeout:
            break

        messages.append(message)

        if _message_matches_action(message, action):
            break

    return messages


def _message_matches_action(message, action):
    action_object = message.get("actionObject") or {}

    return action in {
        message.get("action"),
        message.get("actionType"),
        action_object.get("actionType"),
    }


def _create_id():
    return str(uuid.uuid4())


class _VoicemodWebSocket:
    def __init__(self, host, port, timeout=1.2):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None

    def connect(self):
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(self.timeout)
        self._handshake()

    def close(self):
        if not self.sock:
            return

        try:
            self.sock.close()
        except OSError:
            pass
        finally:
            self.sock = None

    def send_json(self, data):
        self.send_text(json.dumps(data, ensure_ascii=False))

    def recv_json(self):
        text = self.recv_text()

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise VoicemodProtocolError("Voicemod hat ungueltiges JSON gesendet.") from exc

    def send_text(self, text):
        payload = text.encode("utf-8")
        mask_key = os.urandom(4)
        masked_payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))

        if len(payload) < 126:
            header = struct.pack("!BB", 0x81, 0x80 | len(payload))
        elif len(payload) <= 0xFFFF:
            header = struct.pack("!BBH", 0x81, 0x80 | 126, len(payload))
        else:
            header = struct.pack("!BBQ", 0x81, 0x80 | 127, len(payload))

        self.sock.sendall(header + mask_key + masked_payload)

    def recv_text(self):
        chunks = []

        while True:
            first, second = self._read_exact(2)
            fin = bool(first & 0x80)
            opcode = first & 0x0F
            masked = bool(second & 0x80)
            length = second & 0x7F

            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]

            mask_key = self._read_exact(4) if masked else b""
            payload = self._read_exact(length) if length else b""

            if masked:
                payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))

            if opcode == 0x8:
                raise VoicemodProtocolError("Voicemod hat die Verbindung geschlossen.")

            if opcode == 0x9:
                self._send_control_frame(0xA, payload)
                continue

            if opcode == 0xA:
                continue

            if opcode in {0x1, 0x0}:
                chunks.append(payload)

                if fin:
                    return b"".join(chunks).decode("utf-8")

    def _send_control_frame(self, opcode, payload=b""):
        mask_key = os.urandom(4)
        masked_payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        header = struct.pack("!BB", 0x80 | opcode, 0x80 | len(payload))
        self.sock.sendall(header + mask_key + masked_payload)

    def _handshake(self):
        sec_key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            "GET /v1/ HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {sec_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "Origin: http://localhost\r\n"
            "\r\n"
        )

        self.sock.sendall(request.encode("ascii"))
        response = self._read_http_response()
        lines = response.decode("iso-8859-1").split("\r\n")

        if not lines or " 101 " not in lines[0]:
            raise VoicemodProtocolError("Voicemod WebSocket Handshake fehlgeschlagen.")

        headers = {}

        for line in lines[1:]:
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        expected_accept = base64.b64encode(
            hashlib.sha1(f"{sec_key}{WEBSOCKET_GUID}".encode("ascii")).digest()
        ).decode("ascii")

        if headers.get("sec-websocket-accept") != expected_accept:
            raise VoicemodProtocolError("Voicemod WebSocket Antwort war ungueltig.")

    def _read_http_response(self):
        data = b""

        while b"\r\n\r\n" not in data:
            chunk = self.sock.recv(4096)

            if not chunk:
                break

            data += chunk

            if len(data) > 16384:
                raise VoicemodProtocolError("Voicemod Handshake Antwort ist zu gross.")

        return data

    def _read_exact(self, length):
        data = b""

        while len(data) < length:
            chunk = self.sock.recv(length - len(data))

            if not chunk:
                raise VoicemodProtocolError("Voicemod Verbindung wurde unerwartet beendet.")

            data += chunk

        return data
