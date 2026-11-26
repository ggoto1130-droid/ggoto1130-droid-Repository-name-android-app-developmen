# Pokémon White 2 standalone Android app

This repository tracks the Android-specific changes for a single-game Pokémon White 2 app. The melonDS execution core is built into the APK; users do not install or open a separate emulator, and the game starts directly from the app icon.

The game image is user-provided build input and is deliberately excluded from GitHub. Place the verified NDS image at `app/src/main/assets/bundled/pokemon_white2.nds` only in a private build workspace. The expected image is 536,870,912 bytes, has the NDS title `POKEMON W2` and game code `IRDO`, and has SHA-256 `3b3f91fe0e4cc323ea73a1d6242fa04b255d98c4e44971594624bad919713a7b`.

## Diagnosis of the previous APKs

- The v6, v7, and v8 APKs contain the same 7.9 MB melonDS Java/Kotlin application DEX and the same native melonDS libraries. The ROM embedded in v8 matches the launcher's SHA-256 check, so the stored game image is not truncated or corrupted.
- The arm64 melonDS library uses 16 KB-aligned load segments, and the APK targets Android 16. The inspected package and native ABI are compatible with a Pixel 8 at the packaging level.
- Version 1.0.0 crashed while creating its launcher view because it used the splash theme with AppCompat. Version 1.0.1 installs the splash screen before creating any views.
- On Android API 30 and 36, version 1.0.1 showed touchscreen controls over a black first frame with its initial OpenGL/JIT configuration. Both devices rendered the diagnostic cartridge after relaunch in software/interpreter mode. Version 1.0.2 applies this configuration on the first launch and migrates existing installations.
- The previous launcher passes a provider URI through the deprecated `uri` extra. This overlay sends it as `Intent.data`, the supported launch path in the current melonDS source.
- The Android runtime tests use an original test cartridge and verify its two distinct colour bands from screen captures. The privately packaged game uses the user-provided image identified above.

## Build

Run `scripts/build-android.sh` from this repository. The script checks out the pinned melonDS Android source, applies this overlay, and builds the single-game APK. Set `POKEMON_ROM_PATH` to the private, user-provided NDS image for a game-ready build. The GitHub Actions source-check intentionally builds without the game image and does not publish an installable game APK.

The release package ID is `org.syun.pokemonw2.standalone`. Keep that ID and the same private signing key for all future updates; the previous v6/v7/v8 IDs and signing certificates differed, which prevented in-place updates.

The emulator core is melonDS Android, licensed under GPL-3.0. Its upstream source and license are referenced by the build script; no game ROM or BIOS is committed here.
