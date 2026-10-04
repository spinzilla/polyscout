"""All tests fail closed if any code tries to access a real network."""

import socket

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    original_connect = socket.socket.connect
    original_pair = socket.socketpair
    making_pair = False

    def forbidden(*args, **kwargs):
        raise AssertionError("Real network access is forbidden in offline tests")

    def guarded_connect(sock, address):
        # Windows asyncio creates a private loopback socketpair to wake its loop.
        if making_pair and address[0] in {"127.0.0.1", "::1"}:
            return original_connect(sock, address)
        return forbidden()

    def internal_pair(*args, **kwargs):
        nonlocal making_pair
        making_pair = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            making_pair = False

    monkeypatch.setattr(socket, "socketpair", internal_pair)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
