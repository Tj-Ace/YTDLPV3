# YTDLPV3 + Desktop Launcher

Lightweight By Design: **~240KB Core Project Size**.

YTDLPV3 is a Windows desktop downloader built on `yt-dlp` with a custom UI, live terminal log, playlist support, Spotify support, and thumbnail controls.
It also includes a separate desktop launcher for setup, reset, and maintenance tasks.

## What Is Included

- `MainScript.py` (Main Downloader App)
- `Desktop.py` (Desktop Launcher)
- `Config.json` (Saved Settings)
- `Defaults.json` (Reset / fallback defaults)
- `favi.ico` (App Icon)
- `Logs/` (Runtime Log Output)

## Main App Highlights

- Download modes: `Download Videos`, `Download Audio Only`, and `Download Thumbnails Only`
- Optional `Include Thumbnail` toggle
- Optional `Audio As MP4` mode (audio rendered into a black 16:9 MP4)
- Playlist progress display with speed, ETA, elapsed time, and percent
- Spotify links supported through `spotdl` (including playlists)
- aria2c acceleration support with fallback logic
- ffmpeg auto-detect and auto-install support
- Forced image normalization to PNG for thumbnails/output images
- Two UI layouts with persistent layout setting
- Last selected quality is remembered in config

## Desktop Launcher Highlights

- `Auto Install Everything Needed`
- `Create Desktop Shortcut`
- `Pin To Start`
- `Pin To Taskbar`
- `Purge Files` (clears runtime/downloaded dependency folders and non-example logs)
- `Reset Config To Defaults`
- Dependency status panel for `yt-dlp`, `tkinterdnd2`, `aria2c`, and `ffmpeg`
- Built-in launcher terminal log

## Supported Inputs

- YouTube videos, playlists, and channels
- Many generic `yt-dlp` compatible video URLs
- Spotify links (`open.spotify.com`, `spotify.link`)

## Quick Start

1. Install Python 3.10+ on Windows.
2. Open this project folder.
3. Run Desktop.py

## App Workflow Notes

- You must set a download location before starting a download.
- If no location is set, the app prints an error to the terminal and stops.
- Spotify links are treated as audio sources.
- `Download Thumbnails Only` is not supported for Spotify mode.
- `Include Thumbnail` is ignored for Spotify mode.

## Configuration

Settings are saved in `Config.json`.
Default reset/fallback values are read from `Defaults.json`.

Key values:

- `version`
- `layout` (`"1"` or `"2"`)
- `enable_layout_switch_easter_egg` (`false` by default)
- `quality` (`"480p"`, `"720p"`, `"1080p"`, `"Max"`)
- `default_download_location`
- `fullscreen`
- `Accent`
- `Terminal`
- `resolution.width`
- `resolution.height`

## Easter Egg Setting

Double-click layout switching is controlled by config:

- `enable_layout_switch_easter_egg: false` = disabled
- `enable_layout_switch_easter_egg: true` = enabled

## Troubleshooting

- If thumbnails are not converting, verify `ffmpeg` is installed/detected.
- If Spotify downloads fail, verify internet and that `spotdl` installed successfully.
- If acceleration has issues, disable `Use Aria2c Acceleration` and retry.
- If UI behavior feels off after many edits, use launcher `Reset Config To Defaults`.

## Notes

- Thumbnail/image outputs are normalized to PNG.
- Some providers may have site-side limitations or anti-bot behavior.
- The project is intentionally lightweight: **~240KB core size**.
- Yes This Was Vibe Coded, I Know Im Sorry
