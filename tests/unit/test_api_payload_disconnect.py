"""The admitted body is replayed once, then the original ASGI channel resumes."""

import asyncio

from api.request_identity import ProductRequestIdentity
from api.security import ProductSecurityMiddleware


def middleware_for(app, monkeypatch):
    middleware = ProductSecurityMiddleware(app)
    identity = ProductRequestIdentity(
        tenant_id="local", principal="disconnect-test",
        authenticated=False, is_admin=False,
    )
    monkeypatch.setattr(middleware, "_preflight_blocker", lambda request: (None, identity))
    monkeypatch.setattr(middleware, "_audit_request", lambda *args, **kwargs: None)
    monkeypatch.setattr(middleware, "_record_metrics", lambda *args, **kwargs: None)
    return middleware


def scope():
    return {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "path": "/product/test", "raw_path": b"/product/test",
        "root_path": "", "query_string": b"", "headers": [],
        "scheme": "http", "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    }


def test_replay_preserves_chunks_and_delivers_real_disconnect(monkeypatch):
    received, sent = [], []
    messages = iter([
        {"type": "http.request", "body": b"ab", "more_body": True},
        {"type": "http.request", "body": b"cd", "more_body": False},
        {"type": "http.disconnect"},
    ])

    async def receive():
        await asyncio.sleep(0)
        return next(messages)

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        received.extend([await receive(), await receive(), await receive()])
        assert received[-1]["type"] == "http.disconnect"

    asyncio.run(middleware_for(app, monkeypatch)(scope(), receive, send))
    assert [row.get("body") for row in received[:2]] == [b"ab", b"cd"]
    assert sent == []


def test_after_replay_receive_waits_for_the_original_channel(monkeypatch):
    async def scenario():
        released = asyncio.Event()
        calls = 0

        async def receive():
            nonlocal calls
            calls += 1
            if calls == 1:
                return {"type": "http.request", "body": b"", "more_body": False}
            await released.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            pass

        async def app(scope, receive, send):
            assert (await receive())["type"] == "http.request"
            pending = asyncio.create_task(receive())
            await asyncio.sleep(0)
            assert not pending.done(), "body replay must not fabricate endless empty requests"
            released.set()
            assert (await pending)["type"] == "http.disconnect"

        await middleware_for(app, monkeypatch)(scope(), receive, send)
        assert calls == 2

    asyncio.run(scenario())


def test_body_limit_still_applies_after_buffered_replay(monkeypatch):
    from api.config import settings

    monkeypatch.setattr(settings, "product_api_max_payload_bytes", 4)
    messages = iter([
        {"type": "http.request", "body": b"abcd", "more_body": False},
        {"type": "http.request", "body": b"x", "more_body": False},
    ])
    sent = []

    async def receive():
        await asyncio.sleep(0)
        return next(messages)

    async def send(message):
        sent.append(message)

    async def app(scope, receive, send):
        assert (await receive())["body"] == b"abcd"
        await receive()

    asyncio.run(middleware_for(app, monkeypatch)(scope(), receive, send))
    starts = [message for message in sent if message["type"] == "http.response.start"]
    assert len(starts) == 1 and starts[0]["status"] == 413
