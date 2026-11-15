"""Lock In hardware: the only file that touches GPIO.

The server calls exactly three functions: lock(), unlock(), lid_closed().
On a laptop (no GPIO) everything falls back to fake versions that print, so the
whole system can be built and tested without the box.

Wiring (Pi 4 Model B):
    SG90 servo   brown -> pin 6 (GND), red -> pin 2 (5V), orange -> pin 12 (GPIO 18)
    Foil lid     pad A -> pin 16 (GPIO 23), pad B -> pin 14 (GND)

Settings (environment variables):
    LOCKIN_LOCK_ANGLE    servo angle when locked   (default 90)
    LOCKIN_UNLOCK_ANGLE  servo angle when unlocked (default 0)
    LOCKIN_HAS_LID       1 once the foil lid switch is wired (default 0 = lid always closed)
"""
import os
import time

SERVO_PIN = 18
LID_PIN = 23
LOCK_ANGLE = int(os.getenv("LOCKIN_LOCK_ANGLE", "90"))
UNLOCK_ANGLE = int(os.getenv("LOCKIN_UNLOCK_ANGLE", "0"))
HAS_LID = os.getenv("LOCKIN_HAS_LID", "0") == "1"

REAL = False
_servo = None
_lid = None
_fake_lid_closed = True

try:
    from gpiozero import AngularServo, Button

    # SG90 pulse range is roughly 0.5 ms .. 2.5 ms for 0..180 degrees.
    _servo = AngularServo(
        SERVO_PIN,
        min_angle=0,
        max_angle=180,
        min_pulse_width=0.0005,
        max_pulse_width=0.0025,
    )
    _servo.detach()  # no signal until we move: stops buzzing and saves power
    REAL = True
    print(f"[hardware] real GPIO: servo on GPIO{SERVO_PIN}")
except Exception as e:  # not a Pi, or gpiozero missing
    print(f"[hardware] no GPIO ({e.__class__.__name__}: {e}); using FAKE hardware")

if REAL and HAS_LID:
    # Separate on purpose: a broken lid switch must never disable the servo.
    try:
        # Lid closed = foil strip bridges the two pads = pin pulled to GND = "pressed".
        _lid = Button(LID_PIN, pull_up=True, bounce_time=0.05)
        print(f"[hardware] lid sensor on GPIO{LID_PIN}")
    except Exception as e:
        _lid = None
        print(f"[hardware] lid sensor failed ({e}); treating the lid as always closed")


def _move(angle: int) -> None:
    _servo.angle = angle
    time.sleep(0.7)  # SG90 needs ~0.5 s to swing 90 degrees
    _servo.detach()  # stop the PWM signal so the servo doesn't jitter or draw current


def lock() -> None:
    if REAL:
        _move(LOCK_ANGLE)
    print("[hardware] LOCK (latch closed)")


def unlock() -> None:
    if REAL:
        _move(UNLOCK_ANGLE)
    print("[hardware] UNLOCK (latch open)")


def lid_closed() -> bool:
    if REAL and _lid is not None:
        return bool(_lid.is_pressed)
    if REAL:
        return True  # no lid sensor wired yet
    return _fake_lid_closed


def set_fake_lid(closed: bool) -> None:
    """Only used when running without GPIO (testing on a laptop)."""
    global _fake_lid_closed
    _fake_lid_closed = bool(closed)


if __name__ == "__main__":
    # Test block: run `python3 hardware.py` on the Pi.
    print("lid closed?", lid_closed())
    print("locking...")
    lock()
    time.sleep(3)
    print("unlocking...")
    unlock()
    print("lid closed?", lid_closed())
    if HAS_LID:
        print("Open and close the lid; Ctrl+C to stop.")
        last = None
        try:
            while True:
                now = lid_closed()
                if now != last:
                    print("lid", "CLOSED" if now else "OPEN")
                    last = now
                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
