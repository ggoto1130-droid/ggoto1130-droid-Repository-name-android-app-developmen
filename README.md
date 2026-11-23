# Pokémon White 2 standalone Android app

Android source overlay for a single-game app based on the open-source melonDS Android core. The goal is one APK that opens Pokémon White 2 directly; users do not need a separate emulator app or a ROM picker.

The NDS image is private user-provided build input and is intentionally not stored in this public repository. The verified build input is 536,870,912 bytes, title `POKEMON W2`, game code `IRDO`, SHA-256 `3b3f91fe0e4cc323ea73a1d6242fa04b255d98c4e44971594624bad919713a7b`.

## Diagnosis

- The inspected v8 APK contains the expected White 2 image, and its SHA-256 matches the launcher check. The ROM is not truncated or corrupted.
- The v6, v7 and v8 APKs share the same melonDS app DEX and native core. The v8 launcher sets the video renderer to software and leaves JIT disabled, a likely source of severe slowdown on a 512 MB game image.
- The old launcher sends the game URI as a deprecated `uri` extra. This overlay uses the current intent data path.
- The native arm64 library has 16 KB-aligned load segments. Static inspection does not show a Pixel 8 package or ABI mismatch.
- No device crash log is available, so the exact runtime crash is not yet confirmed.

## Status

The source overlay and Android CI compile check are being prepared. CI builds without the private game image and does not publish a playable APK. Do not install its source-check build as the user release.

The release package ID is `org.syun.pokemonw2.standalone`. Keep this ID and the same private signing key for future updates. Previous builds changed package IDs and signing certificates, which blocked in-place updates.

The core is melonDS Android under GPL-3.0. The repository contains no game ROM or BIOS.
