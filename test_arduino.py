"""One-off Arduino test; stop the voice server before using. Never place wheels on floor."""
import argparse
import os
import time

from motor_link import MotorLink

p = argparse.ArgumentParser(description='Safe Arduino USB test with wheels raised')
p.add_argument('command', choices=['?', 'D', 'S', 'F', 'B', 'L', 'R'])
p.add_argument('--wheels-raised', action='store_true', help='Required for all movement commands')
a = p.parse_args()
if a.command in 'FBLR' and not a.wheels_raised:
    p.error('Movement test requires --wheels-raised and safe motor battery wiring')

import serial
port = MotorLink.locate_port()
print('Opening Arduino:', port)
with serial.Serial(port, 9600, timeout=.2, write_timeout=.6) as board:
    time.sleep(1.9)
    board.reset_input_buffer()
    board.write(b'?\n')
    board.flush()
    deadline = time.monotonic() + 3
    verified = False
    while time.monotonic() < deadline:
        line = board.readline().decode('ascii', 'replace').strip()
        if line:
            print('ARDUINO:', line)
        if line == 'PONG_SAFE_V06':
            verified = True
            break
    if not verified:
        raise SystemExit('FAIL: v06 safe Arduino sketch not verified. Do not run motors.')
    board.write((a.command+'\n').encode('ascii'))
    board.flush()
    print('PI SENT:', a.command)
    stop_at = time.monotonic() + (2.0 if a.command in 'FBLR' else 1.2)
    try:
        while time.monotonic() < stop_at:
            line = board.readline().decode('ascii', 'replace').strip()
            if line: print('ARDUINO:', line)
    finally:
        board.write(b'S\n')
        board.flush()
        print('PI SENT: S (stop)')
