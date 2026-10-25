"""
Spotify Ad Skipper (Zero-Dependency & WSL Compatible)
=====================================================================
Detects ads by reading the Spotify desktop window title:
  - Playing a song  -> "Artist - Song"
  - Paused / idle   -> "Spotify Free"
  - Ad playing      -> "Advertisement" (or just "Spotify" on some versions)

When an ad title is seen, Spotify is force-closed and relaunched.
Only uses the Python standard library: no pip install required.
"""

import csv
import ctypes
import io
import os
import subprocess
import sys
import time

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
# Window titles (case-insensitive, exact match) that mean "an ad is playing".
# Do NOT add "Spotify Free"/"Spotify Premium": those mean paused/idle.
AD_TITLES = {"advertisement", "spotify", "listen to music, ad-free."}

# Titles that mean paused/idle (never treated as ads).
IDLE_TITLES = {"spotify free", "spotify premium"}

# Catch-all: songs/podcasts are titled "Artist - Title". If the title does NOT
# contain " - " and isn't an idle title, treat it as an ad. This catches ad
# titles you haven't listed above. Set to False to use AD_TITLES only.
DETECT_BY_PATTERN = True

# Safety: if this many restarts happen within RESTART_WINDOW seconds, pause
# restarting for RESTART_WINDOW seconds (prevents runaway loops).
MAX_RESTARTS = 3
RESTART_WINDOW = 60

POLL_INTERVAL = 2         # seconds between checks
KILL_SETTLE_DELAY = 1.5   # let Windows release file locks
RELAUNCH_COOLDOWN = 10    # grace period after relaunch (prevents boot-loops)

AUTO_PLAY = True          # press the Play media key after Spotify reopens
WINDOW_WAIT = 20          # max seconds to wait for the Spotify window to appear
PLAY_DELAY = 3            # extra seconds after the window appears, so it finishes loading

# ---------------------------------------------------------------------------
# ENVIRONMENT RESOLUTION (Windows & WSL Support)
# ---------------------------------------------------------------------------
IS_WIN32 = sys.platform == "win32"
TASKLIST_CMD = "tasklist" if IS_WIN32 else "tasklist.exe"
TASKKILL_CMD = "taskkill" if IS_WIN32 else "taskkill.exe"

# Resolve Spotify executable paths
try:
    if IS_WIN32:
        user_profile = os.environ.get("USERPROFILE", "")
    else:
        # Fetch Windows environment path from inside WSL
        user_profile = subprocess.run(
            ["cmd.exe", "/c", "echo %USERPROFILE%"], 
            capture_output=True, text=True, check=True
        ).stdout.strip()
    
    win_path = os.path.join(user_profile, r"AppData\Roaming\Spotify\Spotify.exe")
    
    if IS_WIN32:
        SPOTIFY_EXE = win_path
    else:
        # Convert path to WSL standard mount format (/mnt/c/...)
        SPOTIFY_EXE = subprocess.run(
            ["wslpath", win_path], 
            capture_output=True, text=True, check=True
        ).stdout.strip()
except Exception:
    SPOTIFY_EXE = ""

STORE_APP_ID = r"shell:AppsFolder\SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def get_spotify_title():
    """Return the Spotify window title, or None if Spotify isn't running / has no window."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if IS_WIN32 else 0
        out = subprocess.run(
            [TASKLIST_CMD, "/fi", "imagename eq Spotify.exe", "/v", "/fo", "csv", "/nh"],
            capture_output=True, text=True, errors="ignore",
            creationflags=flags
        ).stdout
        
        for row in csv.reader(io.StringIO(out)):
            if len(row) >= 9 and row[0].strip().lower() == "spotify.exe":
                title = row[-1].strip()  # "Window Title" is the last column
                if title and title.upper() != "N/A":
                    return title  # Early exit once target process is found
    except Exception:
        pass
    return None


def kill_spotify() -> None:
    """Force close Spotify process."""
    subprocess.run([TASKKILL_CMD, "/f", "/im", "Spotify.exe"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def launch_spotify() -> None:
    """Launch Spotify via standard build or Microsoft Store fallback."""
    if IS_WIN32:
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        if SPOTIFY_EXE and os.path.isfile(SPOTIFY_EXE):
            subprocess.Popen([SPOTIFY_EXE], creationflags=flags, close_fds=True)
        else:
            subprocess.Popen(["explorer.exe", STORE_APP_ID], creationflags=flags, close_fds=True)
    else:
        # WSL process handling execution
        if SPOTIFY_EXE and os.path.isfile(SPOTIFY_EXE):
            subprocess.Popen([SPOTIFY_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            subprocess.Popen(["explorer.exe", STORE_APP_ID], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def press_play() -> None:
    """Send the keyboard 'Play/Pause' media key (VK_MEDIA_PLAY_PAUSE = 0xB3)."""
    if IS_WIN32:
        try:
            VK_MEDIA_PLAY_PAUSE, KEYUP = 0xB3, 0x0002
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_MEDIA_PLAY_PAUSE, 0, KEYUP, 0)
            return
        except (AttributeError, OSError):
            pass
            
    # Cross-platform WSL Fallback via Windows PowerShell bridge
    powershell_cmd = "$wsh = New-Object -ComObject WScript.Shell; $wsh.SendKeys([char]179)"
    subprocess.run(["powershell.exe", "-Command", powershell_cmd], 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def resume_playback() -> None:
    """Wait for Spotify's window, then trigger the play action."""
    deadline = time.time() + WINDOW_WAIT
    while time.time() < deadline and get_spotify_title() is None:
        time.sleep(1)
    time.sleep(PLAY_DELAY)
    press_play()
    log("Sent Play key sequence")


def looks_like_ad(title) -> bool:
    if not title:
        return False
    t = title.strip().lower()
    if t in IDLE_TITLES:
        return False
    if t in AD_TITLES:
        return True
    return DETECT_BY_PATTERN and " - " not in t


def main() -> None:
    # Environment checks for dependency mappings
    if not IS_WIN32:
        if subprocess.run(["which", "tasklist.exe"], capture_output=True).returncode != 0:
            sys.exit("Error: Cannot find Windows interoperability binaries inside WSL container.")

    if "--show-title" in sys.argv:
        log("Printing Spotify's window title every 2s (Ctrl+C to stop)")
        while True:
            log(repr(get_spotify_title()))
            time.sleep(2)

    log("Monitoring Spotify window title (Ctrl+C to stop)...")
    last_title = object()
    restarts = []
    
    try:
        while True:
            title = get_spotify_title()
            if title != last_title:
                log(f"Title: {title!r}")
                last_title = title

            if looks_like_ad(title):
                now = time.time()
                restarts = [t for t in restarts if now - t < RESTART_WINDOW]
                if len(restarts) >= MAX_RESTARTS:
                    log(f"Too many restarts; pausing {RESTART_WINDOW}s. Verify configurations.")
                    time.sleep(RESTART_WINDOW)
                    restarts.clear()
                    continue
                restarts.append(now)

                log(f"Ad detected (title={title!r}) -> restarting Spotify")
                kill_spotify()
                time.sleep(KILL_SETTLE_DELAY)
                launch_spotify()
                if AUTO_PLAY:
                    resume_playback()
                log(f"Relaunched. Cooling down {RELAUNCH_COOLDOWN}s...")
                time.sleep(RELAUNCH_COOLDOWN)
                last_title = object()
            else:
                time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        log("Stopped.")


if __name__ == "__main__":
    main()
