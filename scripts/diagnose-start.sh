#!/usr/bin/env bash
set -eu
pkg=org.syun.pokemonw2.standalone
mkdir -p diagnostics
adb install -r qa/v101-test-display.apk
adb shell settings put secure immersive_mode_confirmations confirmed
adb shell input keyevent KEYCODE_WAKEUP
adb shell wm dismiss-keyguard || true
adb shell getprop ro.product.cpu.abilist
adb logcat -c
start_app() {
    adb shell am start -W -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n "$pkg/org.syun.pokemonw2.StandaloneLauncherActivity"
}
snapshot() {
    f=$1
    adb exec-out screencap -p > "diagnostics/$f.png"
    adb exec-out screencap | head -c 24 | od -Ax -t u4 > "diagnostics/$f-header.txt" || true
    timeout 8 adb shell uiautomator dump /sdcard/white2-window.xml >/dev/null 2>&1 || true
    adb pull /sdcard/white2-window.xml "diagnostics/$f.xml" >/dev/null 2>&1 || true
    adb shell dumpsys window | grep -E 'mCurrentFocus=|mFocusedApp=' | head -2 || true
    adb shell "run-as $pkg ls -l files; pidof $pkg" || true
    if test -s "diagnostics/$f.xml"; then
        python3 -c 'import sys, xml.etree.ElementTree as E; t=E.parse(sys.argv[1]); print("UI", [(n.get("text"), n.get("content-desc")) for n in t.iter("node") if n.get("text") or n.get("content-desc")][:25])' "diagnostics/$f.xml" || true
    fi
}
start_app
sleep 6
snapshot first
sleep 12
snapshot settled
adb shell am force-stop "$pkg"
start_app
sleep 12
snapshot reopened
adb logcat -d -v threadtime > diagnostics/logcat.txt
adb shell dumpsys activity activities > diagnostics/activities.txt
adb shell "run-as $pkg ls -l -R files shared_prefs" > diagnostics/files.txt || true
grep -Ei 'Failed to launch|PokemonW2Launcher|RomProcessor|EmulatorManager|MelonEmu|melonds_jni|libmelonds|\.game/pokemon|Unable to|FATAL EXCEPTION|Fatal signal|sram|failed to load rom|FileNotFoundException|IllegalStateException|SecurityException|framebuffer|BufferQueue has been abandoned' diagnostics/logcat.txt | tail -75 | cut -c1-320 || true
