# Spotify-Ad-skipper-for-wsl
# Spotify Ad Skipper (Zero-Dependency)

A lightweight, zero-dependency Python script for Windows (and WSL/Ubuntu) that automatically detects Spotify advertisements by monitoring the desktop window title and cleanly restarts the application to skip them.

## 🚀 Features

- **Zero Configuration:** No Spotify Web API keys, developer credentials, or `pip install` setups needed.
- **Pure Python:** Built entirely using the standard library.
- **WSL Compatible:** Runs seamlessly inside Linux environments (WSL Ubuntu) interacting with the Windows host.
- **Anti-Loop Safety:** Built-in safeguards to prevent runaway application launch loops if Spotify updates its titles.

## 🛠️ How It Works

The script queries the active process window manager at regular intervals:
1. **Song Playing:** Title matches `Artist - Song Name` $\rightarrow$ Script sleeps.
2. **Idle/Paused:** Title matches `Spotify Free` or `Spotify Premium` $\rightarrow$ Script sleeps.
3. **Ad Playing:** Title switches to `Advertisement` or generic placeholders $\rightarrow$ The script forces a quick restart of the application and issues a simulated hardware media `Play` key to instantly resume your music.

## 🏃‍♂️ Usage

Simply clone the repository and run the script:

```bash
python spotify_ad_skipper.py
```

### Finding Your Custom Ad Title
If an ad plays and isn't skipped, Spotify may have changed its window title layout in your region. Find the exact string by running:

```bash
python spotify_ad_skipper.py --show-title
```
Copy the string output and add it directly to the `AD_TITLES` set inside the script configuration block.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
