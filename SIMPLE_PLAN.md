# The Lock In plan, in super simple words

No hardware experience needed to read this. Short sentences. One step at a time.

---

## What are we making?

A **box with a lock**.

1. You put your **phone** in the box.
2. You close the lid and press **Start** on the little screen.
3. A tiny robot arm **locks the lid**. A clock counts down.
4. While the clock runs, your **laptop can't open Instagram, TikTok or LinkedIn**.
5. If someone texts you, a **robot helper on Telegram** answers for you.
6. When the clock hits zero, the arm **unlocks the lid**. Everything works again.

That's it. Everything else is details.

---

## The pieces (what each thing is)

| Thing | What it is, simply | It's like… |
|---|---|---|
| **Raspberry Pi** | A tiny computer, the size of a credit card | The **brain** of the box |
| **Touchscreen** | A small screen plugged into the Pi with a flat ribbon cable | The **face** of the box |
| **Servo** | A tiny motor with a plastic arm that turns when the Pi tells it to | A **robot finger** that holds the lid shut |
| **GPIO pins** | The 40 little metal pins sticking up on the Pi | **Plugs** where wires go in |
| **Dupont wires** | Colored wires with little plugs on the ends | **Extension cords** for tiny things |
| **Foil switch** | Two foil pads on the box + one foil strip on the lid | A **doorbell** that rings when the lid touches the box |
| **Speaker** | Plays music | The box's **voice** |
| **Laptop guard** | A small program on the laptop | A **bouncer** that won't let Instagram in |
| **Telegram bot** (@locktf_in_bot) | A robot account on Telegram | Your **secretary** while you study |
| **Gemini** | Google's AI | The secretary's **brain** |

**How they talk:** the Pi and the laptop must be on the **same Wi-Fi**. The laptop keeps asking the Pi
"are we locked?" every 2 seconds. The Pi is the **boss**; everyone else just asks it.

---

## Who does what

| Person | Job in one sentence |
|---|---|
| **A (hardware friend)** | Makes the robot finger lock the lid, and builds the box. |
| **B (Pi friend)** | Makes the Pi start the box program and show it on the screen. |
| **C (laptop friend)** | Puts the bouncer program on the demo laptop. |
| **You (Dimitri)** | Run the Telegram secretary, test the whole story, and do the pitch. |

You don't need to touch the wires. **Your job with hardware is to check it works and keep the team on time.**

---

## The steps, in order

### Step 1. Get on the same Wi-Fi (first 15 minutes, everyone)
- Turn on a **phone hotspot** (a teammate's phone, **not** the phone going in the box).
- Connect the Pi and the laptop to that hotspot.
- On the laptop, open the Pi's address in the browser. If a page loads, they can talk. 🎉
- Why a hotspot? Hackathon Wi-Fi often stops devices from seeing each other.

### Step 2. Everyone builds their piece (11:30 → 1:30)

**A: make the robot finger work**
1. Plug the servo's 3 wires into the Pi:
   - **brown** wire → pin **6** (ground, the "minus")
   - **red** wire → pin **2** (power, the "plus")
   - **orange** wire → pin **12** (the "talk" wire)
2. Run the test: `python3 hardware.py`. The arm should **turn, wait 3 seconds, turn back**.
3. Glue the servo inside the box, on the front wall.
4. Glue a little **tab** (a small piece of plastic) on the **inside of the lid**.
   Locked = the arm turns **under the tab**, so the lid can't open.
5. Optional: the foil "doorbell" so the box knows the lid is closed.

**B: make the screen show the box**
1. Copy the project onto the Pi.
2. Run `./setup_pi.sh` once. It sets everything up.
3. Restart the Pi. The screen should show the **big clock**, to-do list, music and the Start buttons.

**C: put the bouncer on the laptop**
1. On the demo laptop: `./install_mac.sh http://<pi-address>:8000`.
2. It asks for the laptop password **once**.
3. Test: press Start on the box → open instagram.com → **blocked**. In Safari, Chrome and Yandex.

**You: make the secretary work** (already set up; the bot token and Gemini key are saved)
1. Run the bot: `cd agent && .venv/bin/python bot.py`.
2. In Telegram Desktop on the laptop, open **@locktf_in_bot** and send `/start`. Now you're the owner.
3. Ask a friend to text the bot `buy bread on the way home` → "Buy bread" should appear on the box screen.

### Step 3. Check-in at 12:30 (everyone)
Everyone shows **one thing working**. If something is stuck, say it out loud now, not at 3pm.

### Step 4. Big decision at 1:00
- Robot finger works? ✅ Keep going. ❌ Plan B: the screen still says LOCKED, and someone holds the lid on stage.
- Telegram bot works? ✅ Keep going. ❌ Plan B: show it in the backup video.

### Step 5. Put it all together (1:30 → 2:30)
Run the **whole story 3 times**, start to finish:
1. Phone in the box, close the lid, press **1 min**. *Click*, it locks.
2. Open instagram.com on the laptop. **Blocked.**
3. A friend texts the bot "buy bread". It shows up on the box.
4. A friend texts "URGENT call me". The box turns red and offers a free unlock.
5. You text the bot "emergency". The box unlocks. "4 exits left."
6. The timer ends. The box opens, plays a sound, and shows "While you were locked in…".

Before each run: open the **setup page** → press **Refill exits (demo)**.

### Step 6. Make it pretty (2:30 → 3:30)
No new features. Only fix and polish. **Record a backup video** of the whole story.

### Step 7. Submit (3:30 → 4:30)
Devpost page + video + 5 slides. Practice the pitch twice with a timer. **Click Submit by 4:30.**

---

## Questions to ask your hardware friends

Ask these at the start. If anyone says "I don't know", that's the thing to fix first.

1. "Does the **servo move** when we run the test?"
2. "Which **way** does it turn to lock? What **angle** works?" (Write the numbers down and give them to B.)
3. "Are we using the **official Pi charger**?" (A weak charger + servo = the Pi restarts by itself.)
4. "Is the Pi on the **hotspot**? What's its **address**?"
5. "What **size** is the screen?" (Check it says 800×480 or similar.)
6. "Is the **speaker** plugged into the headphone jack, or Bluetooth?"
7. "Does the **phone fit** in the box with the wires inside?"
8. "Do we have a **cardboard backup box** if the plastic cracks?"

---

## If something breaks

| Problem | Do this |
|---|---|
| Laptop can't open the Pi's page | Everyone switches to the phone hotspot. |
| The Pi restarts when the arm moves | Use the official Pi charger. |
| The arm doesn't move | Check the 3 wires: brown → 6, red → 2, orange → 12. |
| The bot doesn't answer | Look at the bot's terminal window for errors. Restart it with `.venv/bin/python bot.py`. |
| Instagram still opens | Press Start **before** opening Instagram. Check the bouncer is installed. |
| Something breaks **on stage** | Don't fix it live. **Play the backup video.** |

---

## Golden rules
1. **Small steps.** Make one tiny thing work, then the next.
2. **Never share the keys.** The bot token and Gemini key live only in `agent/.env`. Not in chat, not on GitHub, not on slides.
3. **Save often.** When something works: commit and push.
4. **After 2:30, no new ideas.** Only fixes.
5. **Never debug on stage.** Backup video.
