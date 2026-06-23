import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from aiohttp import web


STATE = {}
STATE_PATH = Path("logs/esp32_bridge_state.json")


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    global STATE
    try:
        if STATE_PATH.exists():
            payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            devices = payload.get("devices", [])
            STATE = {str(item.get("device_id")): item for item in devices if item.get("device_id")}
    except Exception:
        STATE = {}


def save_state():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    devices = sorted(STATE.values(), key=lambda item: str(item.get("device_id", "")))
    STATE_PATH.write_text(json.dumps({"devices": devices}, ensure_ascii=False), encoding="utf-8")


def normalize_device(payload):
    device_id = payload.get("device_id") or payload.get("id") or payload.get("name") or payload.get("address")
    if not device_id:
        return None

    pins = payload.get("pins") or {}
    if not pins:
        pins = {
            key: value
            for key, value in payload.items()
            if str(key).lower().startswith("gpio")
        }

    normalized_pins = {}
    for key, value in pins.items():
        try:
            normalized_pins[str(key)] = 1 if int(value) else 0
        except Exception:
            normalized_pins[str(key)] = value

    return {
        "device_id": str(device_id),
        "pins": normalized_pins,
        "last_seen": _now_iso(),
    }


def update_from_payload(payload):
    updated = []
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("devices"), list):
        items = payload["devices"]
    else:
        items = [payload]

    for item in items:
        if not isinstance(item, dict):
            continue
        device = normalize_device(item)
        if not device:
            continue
        STATE[device["device_id"]] = device
        updated.append(device)

    if updated:
        save_state()
    return updated


async def button_status(_request):
    return web.json_response({"devices": list(STATE.values())})


async def update_status(request):
    try:
        payload = await request.json()
    except Exception as exc:
        return web.json_response({"status": "error", "message": str(exc)}, status=400)
    updated = update_from_payload(payload)
    return web.json_response({"status": "ok", "updated": len(updated), "devices": updated})


async def websocket_status(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.send_json({"status": "ok", "message": "esp32 bridge connected"})

    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            try:
                payload = json.loads(msg.data)
                updated = update_from_payload(payload)
                await ws.send_json({"status": "ok", "updated": len(updated)})
            except Exception as exc:
                await ws.send_json({"status": "error", "message": str(exc)})
        elif msg.type == web.WSMsgType.ERROR:
            break

    return ws


def create_app():
    app = web.Application()
    app.router.add_get("/esp32/api/button_status/", button_status)
    app.router.add_post("/esp32/api/button_status/", update_status)
    app.router.add_get("/esp32/ws/", websocket_status)
    app.router.add_get("/ws/", websocket_status)
    app.router.add_get("/ws/esp32/buttons/", websocket_status)
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    load_state()
    web.run_app(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
