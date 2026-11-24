# Media Downloader

A standalone desktop application for downloading video, audio (MP3), and image files with automatic ingestion into **DaVinci Resolve**.

## Features
- **Zero-Setup Desktop App:** Packaged for non-technical editors on macOS (`.app`) and Windows (`.exe`)—no Python or Terminal required.
- **Multiple Formats:** Download Video, Audio (MP3), or Images with quality/resolution selection.
- **DaVinci Resolve Integration:** Automatically imports downloaded media directly into your active Resolve Media Pool bin when external scripting is enabled.

## Prerequisites for End Users
1. **FFmpeg** installed on the system (required for merging high-resolution video/audio streams and MP3 conversion).
2. **DaVinci Resolve External Scripting** enabled:
   - Open **DaVinci Resolve > Settings (Preferences) > System > General**
   - Set **External scripting using** to **Local** and click **Save**.
