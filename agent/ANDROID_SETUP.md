# Android phone in the box → the box hears everything

The phone is locked in the box but still connected to Wi-Fi. Every notification it gets
(Instagram, Snapchat, WhatsApp, Telegram, TikTok, LinkedIn, SMS, missed calls) is forwarded to
the box. The agent throws away the junk, Gemini judges the rest, and you only hear about what matters.

```
Android in the box ──MacroDroid──► Pi  POST /inbox ──► agent (every 2 s)
                                                        1. drop junk for free: likes, follows, "is typing", Snaps, "5 new messages"
                                                        2. drop duplicates (Android re-posts the same notification)
                                                        3. Gemini judges the rest in ONE batch call
                                                           urgent    → box turns red + Telegram message RIGHT AWAY
                                                           important → shown on the box + in the 5-min digest (+ to-do)
                                                           noise     → only counted in the end summary
                                                        4. same person 3× in 2 min, or 2 missed calls → bumped up automatically
```

## Setup (15 minutes, on the Android phone)

**Before you start:** the phone and the Pi must be on the **same Wi-Fi/hotspot**. Get the Pi's IP
(on the Pi: `hostname -I`, e.g. `192.168.43.20`). Android often can't open `lockin.local`, so **use the IP**.

1. **Install MacroDroid** from the Play Store (free).
2. Open it → **Add Macro**.
3. **Trigger** → *Device Events* → **Notification** → **Notification Received**
   - Applications: choose **Select Applications** → tick **Instagram, Snapchat, WhatsApp, Telegram, TikTok, LinkedIn, Messages, Phone**
   - Text: *Any content*
   - MacroDroid asks for **Notification access** → allow it.
4. **Action** → *Connectivity* → **HTTP Request**
   - Method: **POST**
   - URL: `http://<PI-IP>:8000/inbox`
   - Body / Content: **Text (text/plain)**, and type **three lines** using the magic-text button (the `...` / `{}` icon):
     ```
     {app name}
     {notification title}
     {notification text}
     ```
     Line 1 = app name, line 2 = notification title, line 3 = notification text. Pick these
     from MacroDroid's magic-text list (names can differ slightly between versions, e.g. `[app_name]`,
     `[notification_title]`, `[notification]`). Plain text lines can't break, even when a message has quotes or emojis.
   - Turn off "block next actions until complete", if shown.
5. Name the macro **Lock In** → save (✓). Make sure it's **enabled**.
6. Android **Settings → Apps → MacroDroid → Battery → Unrestricted** (otherwise Android kills it in the box).
7. Settings → Notifications → lock screen → **show all content / previews** (otherwise texts arrive empty).

## Test it (2 minutes)
1. On the box: tap **25 min**.
2. From another phone, DM the Android on Instagram or WhatsApp: `can you buy bread on the way home?`
3. Within ~3 seconds: the box shows **"1 held from your phone · WhatsApp 1"**, and **Buy bread** appears in the to-do.
4. Send `call me right now, it's an emergency` → the box turns red with **Unlock free**, and you get a 🚨 Telegram message.
5. Like one of its Instagram posts → nothing interrupts you; it's counted in the end summary.

Didn't arrive? Check in this order:
- On the laptop: `curl http://<PI-IP>:8000/inbox`. You should see the notifications listed there.
- MacroDroid → the macro → **Test actions** (sends one test request).
- Same Wi-Fi? Battery set to Unrestricted? Notification access on?

## No phone handy / stage backup
```bash
python3 scripts/simulate_phone.py --pi http://<PI-IP>:8000
```
Plays a realistic 40-second story: Instagram likes and DMs, a Snap, a WhatsApp group, Mom asking for
bread, a professor's room change, then Mom's emergency and a missed call.

## What gets ignored for free (no Gemini call)
Likes, follows, "is live", "posted a new video", story posts, profile views, "is typing", Snaps (photos),
"5 new messages from 3 chats" summaries, backups/downloads, job alerts, MacroDroid and system notifications,
and **our own bot's messages** (so the agent never reads its own replies in a loop).
