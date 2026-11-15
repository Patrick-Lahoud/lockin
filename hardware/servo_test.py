#!/usr/bin/env python3
"""Servo doctor. Run ON THE PI, in the hardware folder:

    python3 servo_test.py            # servo signal on GPIO 18 (physical pin 12)
    python3 servo_test.py 13         # try another GPIO, e.g. GPIO 13 (physical pin 33)
    python3 servo_test.py --rpigpio  # same sweep with a different library (rules out gpiozero)

It checks everything that can stop the servo from moving, in order, and tells you what to fix.
"""
import os
import subprocess
import sys
import time

args = [a for a in sys.argv[1:] if not a.startswith("--")]
PIN = int(args[0]) if args else 18
USE_RPIGPIO = "--rpigpio" in sys.argv
PHYSICAL = {18: 12, 12: 32, 13: 33, 19: 35, 17: 11, 27: 13, 22: 15, 23: 16, 24: 18, 25: 22}


def step(n, text):
    print(f"\n[{n}] {text}")


def ok(text):
    print(f"    ✅ {text}")


def bad(text, fix=""):
    print(f"    ❌ {text}")
    if fix:
        print(f"    → {fix}")


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


print("=== Lock In servo doctor ===")
print(f"Testing the servo signal on GPIO {PIN} = physical pin {PHYSICAL.get(PIN, '?')}")

# 1. Is this a Pi?
step(1, "Is this a Raspberry Pi?")
try:
    model = open("/proc/device-tree/model").read().strip("\x00\n ")
    ok(model)
except OSError:
    bad("This isn't a Raspberry Pi.", "Run this ON the Pi (ssh into it first).")
    sys.exit(1)

# 2. Is the Lock In server holding the pin?
step(2, "Is the Lock In server already using the servo pin?")
if sh(["systemctl", "is-active", "lockin"]) == "active":
    bad("Yes: the lockin service is running and owns the pin, so this test can't move it.",
        "Run:  sudo systemctl stop lockin   then run this test again. (Start it later: sudo systemctl start lockin)")
    sys.exit(1)
others = [l for l in sh(["pgrep", "-af", "server.py|hardware.py"]).splitlines() if str(os.getpid()) not in l]
if others:
    bad("Another program may be using the pin:\n      " + "\n      ".join(others), "Stop it (Ctrl+C in its terminal, or: pkill -f server.py), then run this again.")
    sys.exit(1)
ok("No — the pin is free.")

# 3. Power problems the Pi has recorded
step(3, "Has the Pi seen low voltage? (weak charger + servo = servo won't move or Pi reboots)")
thr = sh(["vcgencmd", "get_throttled"])
if thr:
    try:
        val = int(thr.split("=")[1], 16)
        if val & 0x1:
            bad("Under-voltage RIGHT NOW.", "Use the official 5V 3A Pi charger, not a phone charger/laptop USB.")
        elif val & 0x10000:
            bad("Under-voltage happened since boot (probably when the servo moved).",
                "Use the official 5V 3A Pi charger. If you still have trouble, power the servo from a separate 5V source (GND shared).")
        else:
            ok(f"Power looks fine ({thr}).")
    except (IndexError, ValueError):
        print(f"    (couldn't read: {thr})")
else:
    print("    (vcgencmd not available, skipping)")

# 4. Wiring checklist
step(4, "Wiring: check each wire with your eyes (the #1 cause)")
print(f"""    Servo wire          → Pi PHYSICAL pin (count from the pin with the square pad, pin 1)
    brown / black (GND) → pin 6   (any GND works: 6, 9, 14, 20, 25, 30, 34, 39)
    red (power, 5V)     → pin 2 or 4   ← must be 5V. Pin 1 / 17 is 3.3V: too weak for most servos!
    orange/yellow (sig) → pin {PHYSICAL.get(PIN, '?')}   (= GPIO {PIN}).  NOT "pin 18": GPIO 18 is physical pin 12.
    Pin 1 is the corner pin nearest the SD card side; pins 2,4,6 are on the board-EDGE row.""")

# 5. Sweep
step(5, "Moving the servo now. WATCH IT. (Ctrl+C to stop)")
positions = [("CENTER", 0.0), ("ONE END", -1.0), ("OTHER END", 1.0), ("CENTER", 0.0)]

if USE_RPIGPIO:
    try:
        import RPi.GPIO as GPIO
    except Exception as e:
        bad(f"RPi.GPIO not available ({e})", "sudo apt install -y python3-rpi.gpio   (or run without --rpigpio)")
        sys.exit(1)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN, GPIO.OUT)
    pwm = GPIO.PWM(PIN, 50)  # 50 Hz = standard servo signal
    pwm.start(7.5)
    try:
        for _ in range(2):
            for name, v in positions:
                duty = 7.5 + v * 5.0  # 2.5% .. 12.5% = 0.5 ms .. 2.5 ms
                print(f"    → {name}  (duty {duty:.1f}%)")
                pwm.ChangeDutyCycle(duty)
                time.sleep(1.2)
    finally:
        pwm.stop()
        GPIO.cleanup()
else:
    try:
        from gpiozero import Device, Servo
    except Exception as e:
        bad(f"gpiozero isn't installed for this Python ({e})",
            "Use the Pi's own Python:  /usr/bin/python3 servo_test.py   or:  sudo apt install -y python3-gpiozero python3-lgpio")
        sys.exit(1)
    try:
        servo = Servo(PIN, min_pulse_width=0.0005, max_pulse_width=0.0025)
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"
        fix = "sudo apt install -y python3-lgpio python3-gpiozero"
        if "in use" in msg.lower() or "busy" in msg.lower():
            fix = "Something else owns the pin: sudo systemctl stop lockin   (or reboot), then try again."
        elif "permission" in msg.lower():
            fix = "Add yourself to the gpio group:  sudo usermod -aG gpio $USER   then log out and back in (or run with sudo)."
        bad(f"Couldn't open GPIO {PIN}: {msg}", fix)
        sys.exit(1)
    factory = type(Device.pin_factory).__name__
    print(f"    (gpiozero is driving the pin with {factory})")
    if "Mock" in factory:
        bad("gpiozero is in MOCK mode: it's pretending.", "Remove GPIOZERO_PIN_FACTORY from your environment and run again.")
        sys.exit(1)
    try:
        for _ in range(2):
            for name, v in positions:
                print(f"    → {name}")
                servo.value = v
                time.sleep(1.2)
    finally:
        servo.detach()
        servo.close()

# 6. Verdict
step(6, "What did you see?")
print("""    • It MOVED            → the servo works. If hardware.py still doesn't move it, the angles are too
                             close: try  LOCKIN_LOCK_ANGLE=150 LOCKIN_UNLOCK_ANGLE=30 python3 hardware.py
    • It TWITCHED/BUZZED  → signal is fine, power is too weak: official 3A charger, or a separate 5V
                             supply for the servo's red wire (connect its GND to the Pi's GND too).
    • NOTHING at all      → wiring: recheck step 4 (most often: signal on the wrong pin, or red on 3.3V).
                             Then try another pin:  python3 servo_test.py 13   (move orange to physical pin 33)
                             Then try the other library:  python3 servo_test.py --rpigpio
                             Still nothing → the servo itself may be dead: try a second SG90.""")
