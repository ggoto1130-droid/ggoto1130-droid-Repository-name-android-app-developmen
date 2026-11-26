#!/usr/bin/env python3
"""Exercise the complete Android startup path privately, using original, non-game test graphics."""
from pathlib import Path
import hashlib
import os
import struct
import subprocess
import sys
import time

PACKAGE = "org.syun.pokemonw2.standalone"
CART_SIZE = 512 * 1024 * 1024
PRODUCTION_DIGEST = "3b3f91fe0e4cc323ea73a1d6242fa04b255d98c4e44971594624bad919713a7b"

def crc16(data):
    value = 0xffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return value

def sample_header():
    """Build original ARM code to paint a green and a magenta band on the top DS screen."""
    words, literals = [], []
    def load(register, value):
        literals.append((len(words), register, value))
        words.append(0)
    load(0, 0x04000304)                  # Power control
    load(1, 0x8203)
    words.append(0xe1c010b0)              # strh r1, [r0]
    load(0, 0x04000240)                  # VRAM bank A in LCD mode
    words.extend([0xe3a01080, 0xe5c01000]) # mov r1, #0x80 / strb r1, [r0]
    load(0, 0x04000000)                  # Direct VRAM display
    load(1, 0x20000)
    words.append(0xe5801000)              # str r1, [r0]
    load(1, 0x06800000)
    for rgb555 in (0x83e0, 0xfc1f):
        load(2, rgb555)
        load(3, 256 * 96)
        words.extend([0xe0c120b2, 0xe2533001, 0x1afffffc]) # strh, subs, bne
    words.append(0xeafffffe)              # Halt in a loop
    for position, register, value in literals:
        words[position] = 0xe59f0000 | register << 12 | ((len(words) - position - 2) * 4)
        words.append(value)
    code = struct.pack("<" + "I" * len(words), *words)
    head = bytearray(0x20000)
    # The production fast-path checks these two header identifiers on the second launch.
    # Everything after them is our generated diagnostic cartridge, never an original ROM.
    head[:12] = b"POKEMON W2  "
    head[12:18] = b"IRDO00"
    head[0x14] = 12  # 128 KiB << 12 = 512 MiB
    struct.pack_into("<4I", head, 0x20, 0x200, 0x02000000, 0x02000000, len(code))
    struct.pack_into("<4I", head, 0x30, 0x400, 0x03800000, 0x03800000, 4)
    struct.pack_into("<I", head, 0x68, 0x600)
    struct.pack_into("<2I", head, 0x80, CART_SIZE, 0x200)
    head[0x200:0x200 + len(code)] = code
    struct.pack_into("<I", head, 0x400, 0xeafffffe)  # ARM7 idle loop
    struct.pack_into("<H", head, 0x600, 1)
    text = "Diagnostic display\nCI".encode("utf-16le")
    for language in range(6):
        start = 0x840 + 0x100 * language
        head[start:start + len(text)] = text
    struct.pack_into("<H", head, 0x602, crc16(head[0x620:0xe40]))
    struct.pack_into("<H", head, 0x15c, crc16(head[0xc0:0x15c]))
    struct.pack_into("<H", head, 0x15e, crc16(head[:0x15e]))
    return head

def prepare(checkout):
    launcher = checkout / "app/src/main/java/org/syun/pokemonw2/StandaloneLauncherActivity.kt"
    asset = checkout / "app/src/main/assets/bundled/pokemon_white2.nds"
    if asset.exists():
        raise RuntimeError("Test requires the isolated, ROM-free CI checkout")
    asset.parent.mkdir(parents=True, exist_ok=True)
    with asset.open("xb") as stream:
        stream.write(sample_header())
        stream.truncate(CART_SIZE)
    with asset.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    source = launcher.read_text()
    if source.count(PRODUCTION_DIGEST) != 1:
        raise RuntimeError("CI could not locate the bundled-image digest")
    launcher.write_text(source.replace(PRODUCTION_DIGEST, digest))

def matches_frame(raw):
    if len(raw) < 12:
        return False
    width, height, pixel_format = struct.unpack_from("<3I", raw)
    if pixel_format not in (1, 2) or not (0 < width <= 4096 and 0 < height <= 4096):
        return False
    offset = len(raw) - width * height * 4
    if offset not in (12, 16):
        return False
    green_rows, magenta_rows = [], []
    for y in range(0, height, 4):
        green = magenta = 0
        for x in range(0, width, 8):
            index = offset + (y * width + x) * 4
            r, g, b = raw[index:index + 3]
            if r < 48 and g > 175 and b < 48:
                green += 1
            elif r > 175 and g < 48 and b > 175:
                magenta += 1
        if green >= 8:
            green_rows.append(y)
        if magenta >= 8:
            magenta_rows.append(y)
    return len(green_rows) >= 6 and len(magenta_rows) >= 6 and green_rows[-1] < magenta_rows[0]

def verify(previous, black_screen_release, candidate):
    evidence = Path("qa/evidence")
    evidence.mkdir(parents=True, exist_ok=True)
    adb = str(Path(os.environ["ANDROID_HOME"]) / "platform-tools/adb")
    def call(*args, **kwargs):
        return subprocess.run([adb, *args], check=True, timeout=120, **kwargs)
    def start(tolerate_crash=False):
        subprocess.run([adb, "shell", "am", "start", "-W", "-a", "android.intent.action.MAIN",
                        "-c", "android.intent.category.LAUNCHER", "-n",
                        f"{PACKAGE}/org.syun.pokemonw2.StandaloneLauncherActivity"],
                       check=not tolerate_crash, timeout=90)
    call("shell", "settings", "put", "secure", "immersive_mode_confirmations", "confirmed")
    call("install", "-r", str(previous))
    call("shell", "logcat", "-b", "crash", "-c")
    start(tolerate_crash=True)
    crash = ""
    for _ in range(22):
        crash = call("logcat", "-b", "crash", "-d", capture_output=True, text=True).stdout
        if "Theme.AppCompat" in crash:
            break
        time.sleep(1)
    if "Theme.AppCompat" not in crash:
        raise RuntimeError("The old launcher did not reproduce the expected theme error: " + crash)
    print("PASS: 1.0.0 reproduced the original AppCompat startup exception.", flush=True)
    call("shell", "run-as", PACKAGE, "mkdir", "-p", "files")
    call("shell", "run-as", PACKAGE, "touch", "files/qa-update-marker")
    call("install", "-r", str(black_screen_release))
    start()
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        old_preferences = call("shell", "run-as", PACKAGE, "ls", "files",
                               capture_output=True, text=True).stdout
        if "pokemon_white2.nds" in old_preferences.splitlines():
            break
        time.sleep(1)
    else:
        raise RuntimeError("The intermediate release did not initialise its cartridge")
    prefs_path = f"shared_prefs/{PACKAGE}_preferences.xml"
    old_preferences = call("shell", "run-as", PACKAGE, "cat", prefs_path,
                           capture_output=True, text=True).stdout
    if 'name="video_renderer">opengl<' not in old_preferences:
        raise RuntimeError("Could not reproduce the persisted OpenGL profile")
    call("install", "-r", str(candidate))
    call("shell", "run-as", PACKAGE, "ls", "files/qa-update-marker")
    print("PASS: updates from 1.0.0 through 1.0.1 retained prior app data.", flush=True)

    for run in ("updated", "reopened", "fresh"):
        if run == "fresh":
            call("shell", "pm", "clear", PACKAGE)
        call("shell", "am", "force-stop", PACKAGE)
        start()
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if matches_frame(call("exec-out", "screencap", capture_output=True).stdout):
                (evidence / f"{run}.png").write_bytes(call("exec-out", "screencap", "-p", capture_output=True).stdout)
                print(f"PASS: {run} launcher start rendered both diagnostic bands.", flush=True)
                break
            time.sleep(2)
        else:
            (evidence / f"{run}-failed.png").write_bytes(call("exec-out", "screencap", "-p", capture_output=True).stdout)
            (evidence / f"{run}-logcat.txt").write_bytes(call("logcat", "-d", capture_output=True).stdout)
            call("logcat", "-b", "crash", "-d")
            raise RuntimeError(f"Missing native game frame on {run} launch")

if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare(Path(sys.argv[2]))
    elif sys.argv[1] == "verify":
        verify(Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]))
    else:
        raise SystemExit("Use prepare CHECKOUT or verify OLD_APK INTERMEDIATE_APK CANDIDATE_APK")
