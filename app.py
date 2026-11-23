"""English + Balochi phone microphone -> Raspberry Pi -> guarded Arduino serial.

By default this is a recognition-only demo. Explicit local opt-in is required
before any motor command can reach Arduino Mega.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
import itertools
import logging
from pathlib import Path
import re
from threading import Lock
import time

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from recognizer import BilingualRecognizer
from motor_link import MotorLink

BASE = Path(__file__).resolve().parent
MAX_BYTES = 6_000_000
MODES = {"auto", "english", "balochi"}
ACTIONS = {"F": "FORWARD", "B": "BACKWARD", "L": "LEFT", "R": "RIGHT", "S": "STOP"}
PHONE_UA = re.compile(r"android|iphone|ipad|ipod|mobile", re.IGNORECASE)
SESSION_TTL = 35.0  # allow 3s recording + Pi speech decoding, still expires inactive clients

log = logging.getLogger("robot.voice.simple")
log.setLevel(logging.INFO)
log.propagate = False
if not log.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S"))
    log.addHandler(handler)

recog: BilingualRecognizer | None = None
motor: MotorLink | None = None
counter = itertools.count(1)
state_lock = Lock()
clients: dict[str, dict] = {}
last_event: dict | None = None


class Client(BaseModel):
    client_id: str = Field(min_length=8, max_length=120, pattern=r"^[A-Za-z0-9_-]+$")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def phone_online() -> bool:
    # An active registered web session is the authorization signal, not the
    # User-Agent text (which mobile browsers can disguise).
    return bool(clients)


def cleanup_expired() -> None:
    with state_lock:
        before = phone_online()
        cutoff = time.monotonic() - SESSION_TTL
        for client_id in list(clients):
            if clients[client_id]["last_seen"] < cutoff:
                del clients[client_id]
        if before and not phone_online():
            log.info("VOICE CLIENT DISCONNECTED | registered browser timed out")
            if motor: motor.safe_stop()


async def watch_clients():
    while True:
        await asyncio.sleep(3)
        cleanup_expired()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global recog, motor
    try:
        from vosk import SetLogLevel
        SetLogLevel(-1)
    except ImportError:
        pass
    recog = await asyncio.to_thread(BilingualRecognizer)
    status = recog.status()
    motor = MotorLink()
    await asyncio.to_thread(motor.connect)
    log.info("READY | Balochi=%s | English=%s | Arduino=%s | Waiting for phone",
             "ON" if status.get("balochi_available") else "OFF",
             "ON" if status.get("english_available") else "OFF",
             "CONNECTED" if motor.connected else "OFF")
    if not status.get("english_available"):
        log.warning("ENGLISH MODEL ISSUE | %s", status.get("english_issue") or "unavailable")
    watcher = asyncio.create_task(watch_clients())
    try:
        yield
    finally:
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
        if motor: motor.close()
        log.info("SHUTDOWN | Motors stopped, voice service stopped")


app = FastAPI(title="Simple Bilingual Robot Voice Test", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "index.html").read_text(encoding="utf-8")


def current_state():
    status = recog.status() if recog is not None else {
        "english_available": False, "balochi_available": False,
        "english_issue": "Speech models still loading",
    }
    with state_lock:
        online = phone_online()
        recent = dict(last_event) if last_event else None
    return {
        "server_ready": recog is not None,
        "english_available": status.get("english_available", False),
        "balochi_available": status.get("balochi_available", False),
        "english_issue": status.get("english_issue"),
        "phone_connected": online,
        "latest": recent,
        "arduino_connected": bool(motor and motor.connected),
        "motor_control_enabled": bool(motor and motor.connected),
        "arduino_last_message": motor.last_report if motor else "Not connected",
        "arduino_error": motor.error if motor else None,
    }


@app.get("/status")
def status():
    return current_state()


@app.post("/client/connect")
def client_connect(client: Client, request: Request):
    user_agent = request.headers.get("user-agent", "")
    mobile_hint = bool(PHONE_UA.search(user_agent))
    with state_lock:
        was_online = phone_online()
        clients[client.client_id] = {"phone": mobile_hint, "last_seen": time.monotonic()}
        if not was_online:
            log.info("VOICE CLIENT CONNECTED | Browser session registered (mobile hint=%s)", mobile_hint)
    return current_state()


@app.post("/client/ping")
def client_ping(client: Client):
    with state_lock:
        if client.client_id in clients:
            clients[client.client_id]["last_seen"] = time.monotonic()
    return current_state()


@app.post("/client/disconnect")
def client_disconnect(client: Client):
    with state_lock:
        was_online = phone_online()
        clients.pop(client.client_id, None)
        if was_online and not phone_online():
            log.info("VOICE CLIENT DISCONNECTED | browser closed")
            if motor: motor.safe_stop()
    return {"ok": True}


def record_result(raw: dict, mode: str, client_id: str) -> dict:
    global last_event
    accepted = bool(raw.get("accepted"))
    code = raw.get("candidate_arduino_code") if accepted else None
    language = raw.get("language_detected") if accepted else None
    guesses = []
    for part in raw.get("recognizers") or []:
        guesses.append({
            "language": part.get("language", "unknown"),
            "text": str(part.get("transcript") or "").strip(),
            "score": part.get("score"),
            "accepted": bool(part.get("accepted")),
        })
    heard = str(raw.get("recognized_text") or "").strip()
    with state_lock:
        client = clients.get(client_id)
        authorized_session = bool(client and
                                  time.monotonic() - client["last_seen"] < SESSION_TTL)
    motor_message = "Recognition only — motors are disabled"
    sent = False
    if accepted and motor and motor.connected:
        if not authorized_session:
            motor_message = "Not sent — voice page session expired; refresh your phone page"
        else:
            matching = [g for g in guesses if g["language"] == language and
                        g["accepted"]]
            confidence = float(matching[0]["score"] or 0.0) if matching else 0.0
            required = .90 if language == "balochi" else .80
            if code != 'S' and confidence < required:
                motor_message = f"Not sent — low recognition score ({confidence:.2f} < {required:.2f})"
            else:
                try:
                    motor.send(code)
                    sent = True
                    motor_message = f"Sent {code} to Arduino — check board report"
                except Exception as exc:
                    motor_message = f"USB write failed: {exc}"
                    log.error("ARDUINO ERROR | %s", exc)
    event = {
        "id": next(counter), "time": now_iso(), "mode": mode,
        "accepted": accepted, "language": language,
        "heard": heard if accepted else "",
        "action": ACTIONS.get(code) if accepted else None,
        "code": code, "reason": raw.get("reason") or "No recognized command",
        "guesses": guesses, "simulated": not sent,
        "arduino_sent": sent, "motor_message": motor_message,
    }
    with state_lock:
        last_event = event
    if accepted:
        log.info("VOICE #%03d | ACCEPTED | %s | '%s' -> %s (%s) | %s",
                 event["id"], language.upper() if language else mode.upper(),
                 heard, event["action"], code,
                 "ARDUINO SENT" if sent else motor_message)
    else:
        candidates = " ; ".join(
            f"{x['language']}='{x['text'] or '(none)'}' score={x['score']}"
            for x in guesses
        ) or "no speech candidates"
        log.info("VOICE #%03d | REJECTED | %s | %s | Reason: %s | NO MOTOR ACTION",
                 event["id"], mode.upper(), candidates, event["reason"])
    return event


class ClientError(Client):
    message: str = Field(min_length=1, max_length=300)


@app.post("/client/error")
def client_error(payload: ClientError):
    log.warning("PHONE ERROR | %s | No command processed | Arduino=OFF", payload.message.replace("\n", " "))
    return {"ok": True}


@app.post("/recognize")
async def recognize(file: UploadFile = File(...), mode: str = Form("auto"),
                    client_id: str = Form("")):
    if mode not in MODES:
        raise HTTPException(400, "Choose Auto, English, or Balochi")
    if recog is None:
        raise HTTPException(503, "Voice models are still loading")
    audio = await file.read(MAX_BYTES + 1)
    if len(audio) > MAX_BYTES:
        raise HTTPException(413, "Audio recording is too large")
    if not audio:
        raise HTTPException(400, "No microphone audio received")
    try:
        result = await asyncio.to_thread(recog.analyze, audio, mode)
    except (ValueError, RuntimeError, OSError, TimeoutError) as exc:
        log.warning("VOICE ERROR | %s | %s", mode.upper(), str(exc))
        raise HTTPException(400, f"Could not recognize recording: {exc}") from exc
    except Exception:
        log.exception("VOICE ERROR | Recognition failed (Arduino=OFF)")
        raise HTTPException(500, "Recognition error: check Raspberry Pi terminal") from None
    event = record_result(result, mode, client_id)
    return {"event": event,
            "motor_control_enabled": bool(motor and motor.connected),
            "arduino_sent": event["arduino_sent"]}
