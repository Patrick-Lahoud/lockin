# A: Hardware (the box)

You own `hardware.py`. The server calls only `lock()`, `unlock()`, `lid_closed()`.

## Parts you have
Pi 4 Model B · touchscreen (ribbon) · SG90 servo · Dupont wires · acrylic + box cutter ·
Bluetooth speaker. **Missing:** lid sensor (make one from foil, below) and separate power
(not needed for one SG90).

## 1. Wire the servo
| Servo wire | Pi pin |
|---|---|
| brown | pin 6 (GND) |
| red | pin 2 (5 V) |
| orange | pin 12 (GPIO 18) |

Use the **official 3 A Pi power supply**, not a phone charger. A weak supply + servo = the Pi reboots.

## 2. Test it alone
```bash
cd ~/lock-in/hardware
python3 hardware.py
```
It locks, waits 3 s, unlocks. If the arm swings the wrong way or not far enough, change the angles:
```bash
LOCKIN_LOCK_ANGLE=100 LOCKIN_UNLOCK_ANGLE=10 python3 hardware.py
```
Write the angles that work down and give them to B (they go in the server's systemd service).

## 3. Build the latch
* Hot-glue the servo inside the box, on the front wall, arm pointing up.
* Glue a small tab (acrylic offcut or popsicle stick) on the **inside of the lid**, hanging down.
* Unlocked: the arm points away from the tab. Locked: the arm swings **under/over the tab**, so the lid can't lift.

## 4. Build the lid switch (foil, 15 min)
* Two foil pads on the top edge of the box front, ~5 mm apart, each with a Dupont wire taped under it.
* One foil strip on the lid that touches **both pads** when the lid is closed.
* Pad A → pin 16 (GPIO 23), pad B → pin 14 (GND).
* Test: `LOCKIN_HAS_LID=1 python3 hardware.py`, then open/close the lid and watch it print OPEN/CLOSED.
* When it works, tell B to set `LOCKIN_HAS_LID=1`. Until then the lid always counts as closed.

## 5. Cutting acrylic with a box cutter
Only works on thin sheets (≤ 3 mm), straight lines only. Leave the protective film on, score
the line 8–10 times along a metal ruler, then snap it over the table edge. Don't cut holes;
hot-glue things instead. Hinge = clear packing tape along the back edge.
**Build a cardboard backup box** in case the acrylic cracks.

## No servo working on stage?
The screen still shows LOCKED and the laptop still blocks. Hold the lid shut and keep going.
