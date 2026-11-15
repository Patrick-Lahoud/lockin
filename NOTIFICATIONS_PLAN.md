# How the agent hears WhatsApp, Instagram, TikTok and LinkedIn while the phone is in the box

> Research + plan only. **No code was changed.** Nothing here is committed or pushed.
> Decide as a team, after the MVP works on the real Pi.

---

## The problem, in one line

The phone is locked in the box and Instagram/TikTok/LinkedIn are blocked on the laptop. So **who
is watching your messages?** Today only Telegram is watched, and that only works if people text the bot.

## Think of the agent as a body

| Part | What it is | Today | Goal |
|---|---|---|---|
| **Ears** (senses) | Where messages come in from | Telegram bot only | Telegram + **WhatsApp** + **phone notifications** (Instagram, TikTok, LinkedIn, anything) |
| **Brain** | Gemini decides: urgent? task? summary? | ✅ built, tested, ~1 s | same, nothing changes |
| **Mouth** | Replies to people | Telegram | Telegram + WhatsApp (Instagram/TikTok/LinkedIn are read-only) |
| **Face** | Where **you** see things | box screen + Telegram | **box screen only.** You never open a messaging app. |
| **Hands** | Actions | to-do, urgent alert, unlock, digest | same |

The brain is already done. **We only need more ears.** Every new source becomes the same thing:
`{source, from, text}` → the same Gemini triage → the same box screen. That's why it's an *agent*,
not a bot: one brain, many senses, it acts for you.

---

## Your worry #1: "Telegram makes me open Telegram = distraction"

**Fixed by design, no code needed.** During a session, **the box screen is your only window**:
- urgent messages → the box turns red with **Unlock free**
- 5-minute digests → shown on the box
- emergency exit → **hold the button on the box for 2 s** (already built)
- end-of-session summary → popup on the box

So you never need Telegram open. Telegram stays as (1) the demo channel for "Mom" and (2) an
optional remote control. Say it in the pitch: **"The box is your notification center."**

## Your worry #2: "How do we see Instagram / TikTok / LinkedIn messages?"

**There is no API for personal DMs** on Instagram (the Messaging API is for business accounts with Meta
review), TikTok, or LinkedIn. **The only realistic way is the phone's own notifications.** The phone in
the box still gets every notification. We just need it to **pass them to the box**.

| Phone in the box | How | Covers | Time | Risk |
|---|---|---|---|---|
| **Android** ⭐ | Free app **MacroDroid**: "when a notification arrives → send it to the Pi" (no code on the phone) | WhatsApp, Instagram, TikTok, LinkedIn, SMS, **everything** | **~30 min** | Low |
| **iPhone** | Apple doesn't let apps read other apps' notifications. Options below are all harder. | — | — | — |
| iPhone → Pi Bluetooth (ANCS) | The Pi pretends to be a smartwatch; iPhones send smartwatches every notification. Project: `ancs4linux` | everything | 2–4 h, untested on a Pi | **High.** It also fights the Bluetooth speaker |
| iPhone → Mac (iPhone Mirroring) | macOS 15+: iPhone notifications appear on the Mac even when the phone is far away | everything | 2+ h | **High.** Reading Mac notifications is locked by Apple privacy rules, unverified |
| iPhone → iMessage on the Mac | Mac's Messages database (`chat.db`) gets your iMessages/SMS | iMessage + SMS only | ~1 h | Medium. Needs Full Disk Access; Apple is tightening it |

**Recommendation:** if anyone on the team has an **Android phone**, that phone goes in the box for the
demo. That's the single biggest upgrade: *"the phone in the box tells the box everything."*
If everyone has iPhones, do WhatsApp (below) and pitch the Bluetooth smartwatch trick as the roadmap.

---

## WhatsApp: should we buy a number?

**No. Don't buy a number.**

| Option | Can it read **your** chats? | Needs a number? | Verdict |
|---|---|---|---|
| **Official WhatsApp Cloud API** (Meta / Twilio) | ❌ No. It only sees messages sent **to a business number**. It can't read your personal chats. Meta also banned general-purpose AI chatbots on it from Jan 15, 2026. | yes, a new one | ❌ Wrong tool for us |
| **Linked device** (like WhatsApp Web), library **neonize** (Python) or **whatsapp-web.js** (Node) | ✅ Yes. It sees every chat of the linked account, and can reply as you. Keeps working while the phone is in the box. | **no.** Scan a QR with the existing WhatsApp | ✅ **Use this** |
| Buy a new SIM / virtual number | It's still the linked-device method, just on a fresh account | yes | ❌ Worse: brand-new numbers + automation are the #1 ban trigger, and nobody texts that number |

**Ban risk (honest):** linked-device libraries are unofficial and against WhatsApp's terms. Risk is
driven by behavior, not the library: new numbers, high volume, and messaging people who didn't write
first. Our agent is the safest possible pattern: **an old personal number, only replying once to people
who messaged you, low volume.** Safest of all: **read-only mode** (no auto-replies on WhatsApp), so the
box just shows WhatsApp messages and digests. Link a teammate's account if you don't want to risk yours.

**Which library:** **neonize** (Python, built on the Go library whatsmeow). It fits our Python agent:
no browser, no Node, `pip install neonize`, scan a QR once, session saved in a local SQLite file.

---

## How it plugs in without breaking anything (design, not applied)

Everything is **added**; nothing existing changes. All new ears feed the existing `incoming()` logic.

```
 Android phone in box ──MacroDroid POST──► Pi  POST /inbox  ─┐
                                                             ├─► agent polls GET /inbox ─► Gemini triage ─► /todo /message /digest
 WhatsApp (linked device, neonize) ──────► agent directly ───┤                                          └─► reply (WhatsApp/Telegram only)
 Telegram bot (today) ───────────────────► agent directly ───┘
```

### 1. Pi: one new endpoint (≈20 lines in `pi/server.py`)
```python
# POST /inbox  {"source": "instagram", "from": "alex", "text": "yo are you coming?"}
# The phone in the box (or anything on the Wi-Fi) drops notifications here.
@app.post("/inbox")
async def post_inbox(request: Request):
    data = await body(request)
    item = {"id": secrets.token_hex(4), "source": clean_text(data.get("source"), 20).lower(),
            "from": clean_text(data.get("from"), 40) or "Someone", "text": clean_text(data.get("text"), 500), "at": now()}
    if not item["text"]:
        raise HTTPException(400, "text is required")
    INBOX.append(item)            # INBOX = collections.deque(maxlen=100), in memory
    return {"ok": True}

@app.get("/inbox")
async def get_inbox(after: str = ""):
    items = list(INBOX)
    ids = [i["id"] for i in items]
    return items[ids.index(after) + 1:] if after in ids else items
```
Rate limits already cover it (60/min per IP). Contract change: tell the team out loud first.

### 2. Agent: poll the inbox (≈25 lines in `agent/bot.py`, inside the existing `watch` job)
```python
async def pull_inbox(ctx):
    items = await pi.inbox(after=S.last_inbox_id)          # new GET /inbox call in pi_client.py
    for it in items:
        S.last_inbox_id = it["id"]
        if it["source"] in ("instagram", "tiktok", "linkedin", "whatsapp", "messages"):
            await handle(sender=f"{it['from']} ({it['source'].title()})", text=it["text"], reply=None)
```
`handle()` is today's `incoming()` with the Telegram parts made optional (`reply=None` = read-only:
triage, to-do, urgent alert, digest, no auto-reply).

### 3. WhatsApp ear (new file `agent/whatsapp.py`, ≈60 lines, separate process)
Sketch. **Check the method names against the neonize docs before writing it.**
```python
from neonize.aioze.client import NewAClient
from neonize.aioze.events import MessageEv
wa = NewAClient("whatsapp_session.sqlite3")   # git-ignore this file: it IS your WhatsApp login

@wa.event(MessageEv)
async def on_msg(client, ev: MessageEv):
    if ev.Info.MessageSource.IsFromMe or ev.Info.MessageSource.IsGroup:
        return                                  # ignore yourself and groups
    text = ev.Message.conversation or ev.Message.extendedTextMessage.text
    await pi_post_inbox(source="whatsapp", sender=ev.Info.Pushname, text=text)   # read-only mode
    # optional reply mode: await client.reply_message("Locked in until 15:00…", ev)
```
Simplest + safest: the WhatsApp ear **just posts to `/inbox`** like the phone does, so the brain code
doesn't change at all.

### 4. Android phone in the box (no code, ~30 min)
1. Install **MacroDroid** (Play Store, free).
2. Allow **Notification access** when it asks. Turn **off battery optimization** for MacroDroid.
3. New macro → **Trigger:** Notification → *Notification Received* → apps: WhatsApp, Instagram, TikTok, LinkedIn, Messages.
4. **Action:** HTTP Request → **POST** → `http://<PI-IP>:8000/inbox` (use the IP; Android often can't open `.local` names)
   → body type JSON → `{"source":"[app_name]","from":"[notification_title]","text":"[notification]"}`
   (pick these from MacroDroid's "magic text" list).
5. Test: someone DMs that phone on Instagram → it appears on the box within seconds.
6. Phone settings → notifications → **show previews: always**, or the text arrives empty.

---

## What to do with 4 hours left (honest)

| When | What | Why |
|---|---|---|
| **Now → +1:30** | Make the **current MVP work on the real Pi**: servo, screen, laptop blocking, Telegram bot. | Nothing else matters if the box doesn't lock on stage. |
| **+1:30 → +2:15** | **One** new ear: **Android + MacroDroid** if anyone has Android (best). Otherwise **WhatsApp via neonize, read-only.** | One working wow moment beats three half-working ones. |
| **+2:15** | Feature freeze. Run the full demo 3× and record the backup video. | |
| Pitch | Roadmap slide: "iPhone support via Bluetooth, the box acts like a smartwatch (ANCS)". | Shows you know how to finish it. |

### Ask the team right now
1. **Does anyone have an Android phone** we can put in the box for the demo?
2. Whose **WhatsApp** are we OK linking (risk: unofficial client)?
3. Is the demo Mac on **macOS 15 or newer**? (only matters for the iPhone/Mac ideas)

### New demo moment
> "My phone is locked in the box. Watch: Alex DMs me on **Instagram**. The box hears it through the
> phone's own notifications. Gemini says it's not urgent and summarizes it. Now Mom texts **WhatsApp**:
> 'URGENT call me'. The box turns red and offers a free unlock. **I never touched my phone or opened an app.**"

---

### Sources
* WhatsApp unofficial libraries, ban risk and 2026 chatbot policy: [checkleaked: Cloud API vs unofficial](https://whatsapp.checkleaked.cc/de/blog/whatsapp-cloud-api-vs-unofficial), [best open-source WhatsApp libraries 2026](https://whatsapp.checkleaked.cc/blog/best-open-source-whatsapp-libraries), [zylos: WhatsApp API & automation 2026](https://zylos.ai/zh/research/2026-01-26-whatsapp-api-automation)
* Cloud API can't read existing personal chats: [Meta: onboarding Business App users](https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users), [Blueticks: reading WhatsApp chats via API](https://blueticks.co/blog/whatsapp-api-read-messages-and-chats)
* neonize (Python, whatsmeow): [PyPI](https://pypi.org/project/neonize/)
* iPhone notifications over Bluetooth: [ancs4linux](https://github.com/pzmarzly/ancs4linux), [ble-ancs](https://github.com/robotastic/ble-ancs)
* Android forwarding: [MacroDroid Notification trigger](https://macrodroidforum.com/wiki/index.php/Trigger:_Notification), [IFTTT Android notification → webhook](https://ifttt.com/applets/mL9ABJqb-send-a-webhooks-request-when-an-android-notification-arrives)
* iPhone Mirroring notifications on Mac: [Apple support](https://support.apple.com/120421); protected notification DB in Sequoia: [9to5Mac](https://9to5mac.com/2024/09/01/security-bite-apple-addresses-privacy-concerns-around-notification-center-database-in-macos-sequoia/)
* iMessage on Mac (`chat.db`, attributedBody, AppleScript sending): [jons-mcp-imessage DB format](https://glama.ai/mcp/servers/@jonmmease/jons-mcp-imessage/blob/3af876d28c0efe9f24b18db9936155308736c4b9/docs/IMESSAGE_DATABASE_FORMAT.md), [imessage-kit](https://photon.codes/docs/opensource/imessage-kit)
