#!/usr/bin/env python3
"""Lock In laptop guard: blocks sites in EVERY browser and quits apps while the box is locked.

Built on the Shutout approach (a marked section in the hosts file), but instead of asking
for the admin password every session, it runs as a background service installed once.
It follows the box: GET <pi>/state every 2 s.

Modes
  system   run as root (launchd / Task Scheduler). Writes/removes the LOCKIN section of the
           hosts file, flushes DNS, quits blocked apps. Works for Safari, Chrome, Yandex,
           Firefox, Edge and every desktop app, because the OS itself can't resolve the sites.
  tabs     run as you (macOS only). Sends tabs that are ALREADY open on a blocked site to the
           box's own screen (Safari, Chrome, Yandex, Edge, Brave, Arc, Chromium, Vivaldi).
  screen   run as you. While the box is locked, shows the Pi's screen in a borderless window,
           so the computer looks exactly like the box. Closes it again on unlock.
  clear    remove the LOCKIN section once and exit (used by the uninstaller).

Fail closed: if the Pi can't be reached mid-session, keep blocking until ends_at, then open.

Stdlib only, so it runs on any python3 with no pip install.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

IS_MAC = sys.platform == "darwin"
IS_WIN = os.name == "nt"

if IS_WIN:
    HOSTS_FILE = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "drivers" / "etc" / "hosts"
    DATA_DIR = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "LockIn"
elif IS_MAC:
    HOSTS_FILE = Path("/etc/hosts")
    DATA_DIR = Path("/Library/Application Support/LockIn")
else:
    HOSTS_FILE = Path("/etc/hosts")
    DATA_DIR = Path("/etc/lockin")

BEGIN = "# LOCKIN-BEGIN (managed by Lock In, do not edit)"
END = "# LOCKIN-END"
POLL_SECONDS = 1
DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$")
APP_RE = re.compile(r"^[A-Za-z0-9 ._-]{1,40}$")

# hosts files have no wildcards, so list the subdomains that actually serve each app.
EXTRA_HOSTS = {
    "instagram.com": ["i.instagram.com", "l.instagram.com", "graph.instagram.com", "help.instagram.com", "about.instagram.com", "static.cdninstagram.com"],
    "tiktok.com": ["vm.tiktok.com", "vt.tiktok.com", "m.tiktok.com", "us.tiktok.com", "t.tiktok.com"],
    "linkedin.com": ["ca.linkedin.com", "static.licdn.com", "media.licdn.com"],
    "youtube.com": ["youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com", "music.youtube.com", "youtubei.googleapis.com"],
    "x.com": ["twitter.com", "www.twitter.com", "mobile.twitter.com", "api.x.com", "t.co", "abs.twimg.com", "pbs.twimg.com"],
    "twitter.com": ["mobile.twitter.com", "t.co", "abs.twimg.com"],
    "reddit.com": ["old.reddit.com", "new.reddit.com", "redd.it", "i.redd.it", "v.redd.it", "www.redditstatic.com"],
    "facebook.com": ["web.facebook.com", "fb.com", "www.fb.com", "static.xx.fbcdn.net"],
    "netflix.com": ["assets.nflxext.com"],
}

# macOS browsers that can be scripted (Firefox can't, but the hosts block still covers it).
SCRIPTABLE_BROWSERS = ["Safari", "Google Chrome", "Yandex", "Microsoft Edge", "Brave Browser", "Arc", "Chromium", "Vivaldi"]


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


# ---------------------------------------------------------------- config + state
def load_config(args) -> dict:
    cfg = {"pi_url": "http://lockin.local:8000"}
    try:
        cfg.update(json.loads((DATA_DIR / "config.json").read_text()))
    except Exception:
        pass
    if args.pi:
        cfg["pi_url"] = args.pi
    cfg["pi_url"] = cfg["pi_url"].rstrip("/")
    return cfg


# Never route the box through a system proxy/VPN: it's on the local network.
_DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def fetch_state(pi_url: str):
    try:
        with _DIRECT.open(f"{pi_url}/state", timeout=1.5) as r:
            data = json.loads(r.read().decode())
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def valid_domains(raw) -> list:
    out = []
    for d in raw or []:
        d = str(d).strip().lower()
        if DOMAIN_RE.match(d):
            out.append(d)
    return out


def valid_apps(raw) -> list:
    return [a for a in (str(x).strip() for x in raw or []) if APP_RE.match(a)]


def expand(domains: list) -> list:
    hosts = []
    for d in domains:
        hosts += [d, f"www.{d}", f"m.{d}"] + EXTRA_HOSTS.get(d, [])
    return [h for h in dict.fromkeys(hosts) if DOMAIN_RE.match(h)]


class Session:
    """What we should be blocking right now, with a fail-closed cache on disk."""

    def __init__(self, cache_path: Path, writable: bool):
        self.cache_path = cache_path
        self.writable = writable
        self.reachable = None

    def read_cache(self):
        try:
            return json.loads(self.cache_path.read_text())
        except Exception:
            return None

    def write_cache(self, value):
        if not self.writable:
            return
        try:
            if value is None:
                self.cache_path.unlink(missing_ok=True)
            else:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                self.cache_path.write_text(json.dumps(value))
        except Exception as e:
            log("cache write failed:", e)

    def current(self, pi_url: str) -> dict:
        """Returns {"locked": bool, "domains": [...], "apps": [...], "ends_at": int|None}."""
        s = fetch_state(pi_url)
        if (s is not None) != self.reachable:
            self.reachable = s is not None
            log("Pi", "reachable" if self.reachable else f"UNREACHABLE at {pi_url}")
        if s is not None:
            locked = s.get("mode") == "locked"
            info = {
                "locked": locked,
                "domains": valid_domains(s.get("blocked_sites")),
                "apps": valid_apps(s.get("blocked_apps")),
                "ends_at": s.get("ends_at"),
            }
            self.write_cache(info if locked else None)
            return info
        cached = self.read_cache()  # Pi unreachable: fail closed until the session would have ended
        if cached and cached.get("ends_at") and time.time() < cached["ends_at"]:
            return {**cached, "locked": True}
        return {"locked": False, "domains": [], "apps": [], "ends_at": None}


# ---------------------------------------------------------------- the box screen
# The screen runs as the logged-in user, so its browser profile has to live somewhere
# that user can write (ProgramData is read-only for non-admins).
if IS_WIN:
    USER_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "LockIn"
elif IS_MAC:
    USER_DIR = Path.home() / "Library" / "Application Support" / "LockIn"
else:
    USER_DIR = Path.home() / ".local" / "share" / "lockin"
SCREEN_PROFILE = USER_DIR / "screen-profile"


def find_screen_browser():
    """A Chrome-family binary that can open an app window, or None."""
    if IS_WIN:
        for path in (
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ):
            if os.path.exists(path):
                return path
        return None
    if IS_MAC:
        for app in ("Google Chrome", "Microsoft Edge", "Brave Browser", "Chromium"):
            path = f"/Applications/{app}.app/Contents/MacOS/{app}"
            if os.path.exists(path):
                return path
        return None
    for name in ("chromium", "chromium-browser", "google-chrome", "microsoft-edge"):
        path = shutil.which(name)
        if path:
            return path
    return None


class BoxScreen:
    """The Pi's screen, mirrored in a borderless window on this computer.

    It points at the Pi's own /, so there is no second copy of the UI to drift:
    whatever the box shows, this shows. A private user-data-dir keeps it in its
    own process, so closing it never touches the browser you are actually using.
    """

    def __init__(self, pi_url: str):
        self.url = pi_url.rstrip("/") + "/"
        self.proc = None
        self.warned = False

    def is_open(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def open(self) -> None:
        if self.is_open():
            return
        browser = find_screen_browser()
        if not browser:
            if not self.warned:
                self.warned = True
                log("no Chrome or Edge found, so the box screen can't be shown here")
            return
        try:
            SCREEN_PROFILE.mkdir(parents=True, exist_ok=True)
            self.proc = subprocess.Popen(
                [
                    browser,
                    f"--app={self.url}",
                    "--start-fullscreen",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--autoplay-policy=no-user-gesture-required",
                    f"--user-data-dir={SCREEN_PROFILE}",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            log(f"box screen open: {self.url}")
        except Exception as e:
            log("couldn't open the box screen:", e)

    def close(self) -> None:
        if self.is_open():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
            log("box screen closed")
        self.proc = None


def run_screen(args, cfg) -> None:
    """Keep a window showing the Pi's screen open exactly while the box is locked."""
    # read the cache the root guard writes, so the screen also stays up if the Pi drops mid-session
    session = Session(Path(args.cache) if args.cache else DATA_DIR / "cache.json", writable=False)
    screen = BoxScreen(cfg["pi_url"])
    log(f"guard (screen) mirroring {cfg['pi_url']}")
    try:
        while True:
            info = session.current(cfg["pi_url"])
            if info["locked"] and not screen.is_open():
                screen.open()
            elif not info["locked"] and screen.is_open():
                screen.close()
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        screen.close()


# ---------------------------------------------------------------- hosts file (root)
def strip_section(text: str) -> str:
    out, skip = [], False
    for line in text.splitlines():
        if line.startswith("# LOCKIN-BEGIN"):
            skip = True
            continue
        if line.strip() == END:
            skip = False
            continue
        if not skip:
            out.append(line)
    return "\n".join(out).rstrip("\n") + "\n"


def build_hosts(current: str, hosts: list) -> str:
    clean = strip_section(current)
    if not hosts:
        return clean
    lines = [BEGIN] + [f"0.0.0.0 {h}\n::1 {h}" if not IS_WIN else f"0.0.0.0 {h}" for h in hosts] + [END]
    return clean + "\n".join(lines) + "\n"


def write_hosts(path: Path, content: str) -> None:
    st = path.stat() if path.exists() else None
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".lockin-hosts.")
    try:
        with os.fdopen(fd, "w", newline="\r\n" if IS_WIN else "\n") as f:
            f.write(content)
        if st and not IS_WIN:
            os.chmod(tmp, st.st_mode & 0o777)
            try:
                os.chown(tmp, st.st_uid, st.st_gid)
            except PermissionError:
                pass
        os.replace(tmp, path)  # atomic, like Shutout's mv -f
    except PermissionError:
        os.unlink(tmp)
        if IS_WIN:  # Windows sometimes refuses replace on hosts; write in place instead
            path.write_text(content, newline="\r\n")
        else:
            raise
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def flush_dns() -> None:
    cmds = [["ipconfig", "/flushdns"]] if IS_WIN else [["dscacheutil", "-flushcache"], ["killall", "-HUP", "mDNSResponder"]] if IS_MAC else [["resolvectl", "flush-caches"]]
    for c in cmds:
        subprocess.run(c, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def apply_block(hosts_path: Path, hosts: list, flush: bool) -> bool:
    """Returns True if the file changed."""
    current = hosts_path.read_text() if hosts_path.exists() else ""
    wanted = build_hosts(current, hosts)
    if wanted == current:
        return False
    write_hosts(hosts_path, wanted)
    if flush:
        flush_dns()
    return True


def quit_apps(apps: list) -> None:
    for a in apps:
        name = a.removesuffix(".app").removesuffix(".exe")
        if IS_WIN:
            cmd = ["taskkill", "/F", "/IM", f"{name}.exe"]
        else:
            cmd = ["pkill", "-x", name]
        r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        if r.returncode == 0:
            log(f"quit app: {name}")


def run_system(args, cfg) -> None:
    hosts_path = Path(args.hosts_file) if args.hosts_file else HOSTS_FILE
    session = Session(Path(args.cache) if args.cache else DATA_DIR / "cache.json", writable=True)
    log(f"guard (system) watching {cfg['pi_url']}, hosts file {hosts_path}")
    was_locked = None
    while True:
        try:
            info = session.current(cfg["pi_url"])
            hosts = expand(info["domains"]) if info["locked"] else []
            if apply_block(hosts_path, hosts, flush=not args.no_flush):
                log(f"BLOCKED {len(hosts)} hosts: {', '.join(info['domains'])}" if hosts else "UNBLOCKED: hosts section removed")
            if info["locked"] != was_locked:
                was_locked = info["locked"]
                log("box is", "LOCKED" if was_locked else "idle")
            if info["locked"] and info["apps"]:
                quit_apps(info["apps"])
        except Exception as e:
            log("error:", e)
        if args.once:
            return
        time.sleep(POLL_SECONDS)


# ---------------------------------------------------------------- open tabs (macOS user)
def running(app: str) -> bool:
    return subprocess.run(["pgrep", "-x", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def as_str(s: str) -> str:
    # AppleScript string literal; inputs are validated ASCII URLs.
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def tab_script(app: str, prefixes: list, targets: list) -> str:
    return f"""
set prefixes to {{{", ".join(as_str(p) for p in prefixes)}}}
set targets to {{{", ".join(as_str(t) for t in targets)}}}
set kicked to 0
tell application "{app}"
  repeat with w in windows
    repeat with t in tabs of w
      try
        set u to URL of t
        repeat with i from 1 to count of prefixes
          if u starts with (item i of prefixes) then
            set URL of t to (item i of targets)
            set kicked to kicked + 1
            exit repeat
          end if
        end repeat
      end try
    end repeat
  end repeat
end tell
return kicked
"""


def run_tabs(args, cfg) -> None:
    if not IS_MAC:
        log("tab guard is macOS-only; the hosts block still covers every browser")
        return
    session = Session(DATA_DIR / "cache.json", writable=False)
    denied = set()
    log(f"guard (tabs) watching {cfg['pi_url']}")
    while True:
        try:
            info = session.current(cfg["pi_url"])
            if info["locked"]:
                prefixes, targets = [], []
                for d in info["domains"]:
                    page = f"{cfg['pi_url']}/"  # the box's own screen, so both look the same
                    for h in [d, f"www.{d}", f"m.{d}"] + EXTRA_HOSTS.get(d, []):
                        for scheme in ("https", "http"):
                            prefixes.append(f"{scheme}://{h}/")
                            targets.append(page)
                for app in SCRIPTABLE_BROWSERS:
                    if app in denied or not prefixes or not running(app):
                        continue
                    r = subprocess.run(["osascript", "-e", tab_script(app, prefixes, targets)], capture_output=True, text=True, timeout=10)
                    if r.returncode != 0:
                        if "-1743" in r.stderr or "not authorized" in r.stderr.lower():
                            denied.add(app)
                            log(f"{app}: Automation permission denied. Allow it in System Settings → Privacy & Security → Automation")
                        else:
                            log(f"{app}: {r.stderr.strip()[:160]}")
                    elif r.stdout.strip() not in ("", "0"):
                        log(f"{app}: sent {r.stdout.strip()} open tab(s) to the Locked In page")
        except Exception as e:
            log("error:", e)
        if args.once:
            return
        time.sleep(POLL_SECONDS)


# ---------------------------------------------------------------- main
def main() -> None:
    p = argparse.ArgumentParser(description="Lock In laptop guard")
    p.add_argument("mode", choices=["system", "tabs", "screen", "clear"])
    p.add_argument("--pi", help="Pi URL, e.g. http://lockin.local:8000 (default: config.json)")
    p.add_argument("--hosts-file", help="use a different hosts file (for testing without sudo)")
    p.add_argument("--cache", help="cache file path (for testing without sudo)")
    p.add_argument("--no-flush", action="store_true", help="don't flush DNS (testing)")
    p.add_argument("--once", action="store_true", help="run one cycle and exit")
    args = p.parse_args()
    cfg = load_config(args)

    if args.mode == "clear":
        path = Path(args.hosts_file) if args.hosts_file else HOSTS_FILE
        if apply_block(path, [], flush=not args.no_flush):
            log("hosts section removed")
        (Path(args.cache) if args.cache else DATA_DIR / "cache.json").unlink(missing_ok=True)
        return
    if args.mode == "system":
        run_system(args, cfg)
    elif args.mode == "screen":
        run_screen(args, cfg)
    else:
        run_tabs(args, cfg)


if __name__ == "__main__":
    main()
