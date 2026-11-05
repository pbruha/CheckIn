"""Ověří skutečné Web Push odesílání (pywebpush) proti lokálnímu HTTP endpointu.

Chytá např. chybu, kdy se PEM klíč předával jako řetězec, který knihovna nepřijme.
"""
from __future__ import annotations

import base64
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid01

from app.config import Settings
from app.push import default_sender


def test_real_sender_signs_and_encrypts_request():
    received: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            received["headers"] = {k.lower(): v for k, v in self.headers.items()}
            received["body"] = self.rfile.read(length)
            self.send_response(201)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        vapid = Vapid01()
        vapid.generate_keys()
        settings = Settings(
            vapid_private_key=vapid.private_pem().decode(),
            vapid_public_key="unused-here",
            vapid_subject="mailto:test@example.org",
        )
        client_key = ec.generate_private_key(ec.SECP256R1())
        p256dh = base64.urlsafe_b64encode(
            client_key.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
            )
        ).decode().rstrip("=")
        auth = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip("=")
        info = {"endpoint": f"http://127.0.0.1:{server.server_port}/push/abc", "keys": {"p256dh": p256dh, "auth": auth}}

        default_sender(info, json.dumps({"title": "Test", "body": "x", "url": "/"}), settings)

        headers = received["headers"]
        assert headers["authorization"].startswith("WebPush ")
        assert "p256ecdsa=" in headers["crypto-key"]
        assert headers["content-encoding"] == "aes128gcm"
        assert b"Test" not in received["body"]  # payload je šifrovaný
    finally:
        server.shutdown()
