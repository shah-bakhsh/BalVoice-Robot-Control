"""Guarded Arduino Mega serial bridge. No motor operation unless explicitly enabled.

Only the included safe-boot Arduino v06 sketch is accepted by firmware handshake.
"""
import logging
import os
from pathlib import Path
import threading
import time

log = logging.getLogger('robot.voice.simple')


class MotorLink:
    def __init__(self):
        self.enabled = (os.environ.get('ROBOT_ENABLE_MOTORS') == '1'
                        and os.environ.get('ROBOT_SAFE_SKETCH_CONFIRMED') == 'YES')
        self.ser = None
        self.port = None
        self.error = None
        self.last_report = 'Not connected'
        self._lock = threading.RLock()
        self._shutdown = threading.Event()
        self._reader_thread = None

    @staticmethod
    def locate_port():
        specified = os.environ.get('ROBOT_PORT', '').strip()
        if specified:
            return specified
        candidates = [str(p) for p in Path('/dev/serial/by-id').glob('*') if 'Arduino' in p.name]
        if len(candidates) != 1:
            raise RuntimeError(f'Expected one Arduino in /dev/serial/by-id, found {len(candidates)}')
        return candidates[0]

    @property
    def connected(self):
        return bool(self.ser and self.ser.is_open and not self._shutdown.is_set())

    def connect(self):
        if not self.enabled:
            self.last_report = 'Motors disabled by default. Recognition only.'
            return
        try:
            import serial
            self.port = self.locate_port()
            self.ser = serial.Serial(self.port, 9600, timeout=.2, write_timeout=.5)
            # The Arduino Mega may reboot as this port opens.
            time.sleep(1.9)
            self.ser.reset_input_buffer()
            self.ser.write(b'?\n')
            self.ser.flush()
            until = time.monotonic() + 3.0
            valid = False
            while time.monotonic() < until:
                line = self.ser.readline().decode('ascii', 'replace').strip()
                if line == 'PONG_SAFE_V06':
                    valid = True
                    break
            if not valid:
                raise RuntimeError('Arduino did not confirm safe v06 firmware. Upload the included sketch first.')
            self._shutdown.clear()
            self.send('S')
            self.send('V')
            self.last_report = 'Safe Arduino v06 connected; stopped'
            log.info('ARDUINO CONNECTED | %s | SAFE FIRMWARE VERIFIED', self.port)
            self._reader_thread = threading.Thread(target=self._reader, name='arduino-reader', daemon=True)
            self._reader_thread.start()
        except Exception as exc:
            self.error = f'{type(exc).__name__}: {exc}'
            log.error('ARDUINO NOT READY | %s | MOTOR CONTROL DISABLED', self.error)
            self.enabled = False
            self._shutdown.set()
            if self.ser:
                try: self.ser.close()
                except Exception: pass
                self.ser = None

    def _reader(self):
        while not self._shutdown.is_set():
            try:
                message = self.ser.readline().decode('ascii', 'replace').strip()
                if message:
                    self.last_report = message[:160]
                    log.info('ARDUINO | %s', self.last_report)
            except Exception as exc:
                self.error = f'USB serial connection lost: {exc}'
                self._shutdown.set()
                log.error('ARDUINO DISCONNECTED | %s | RECONNECT ONLY AFTER SAFETY CHECK', self.error)
                break

    def send(self, code: str):
        if code not in {'F', 'B', 'L', 'R', 'S', 'V'}:
            raise ValueError('Unsupported command')
        with self._lock:
            if not self.connected:
                raise RuntimeError(self.error or 'Arduino not connected or not enabled')
            try:
                self.ser.write((code+'\n').encode('ascii'))
                self.ser.flush()
                log.info('ARDUINO SENT | %s', code)
            except Exception as exc:
                self.error = str(exc)
                self._shutdown.set()
                raise RuntimeError(f'USB write failed: {exc}') from exc

    def safe_stop(self):
        if self.connected:
            try: self.send('S')
            except Exception as exc: log.warning('STOP WRITE FAILED | %s', exc)

    def close(self):
        self.safe_stop()
        self._shutdown.set()
        if self.ser:
            try: self.ser.close()
            except Exception: pass
            self.ser = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=.5)

    def status(self):
        return {'connected': self.connected,
                'enabled': self.enabled and self.connected,
                'port': self.port, 'last_report': self.last_report,
                'error': self.error}
