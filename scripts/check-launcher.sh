#!/usr/bin/env bash
# Exercises the launcher on a clean Android installation using the public, ROM-free build.
set -euo pipefail
apk=${1:?Pass the ROM-free APK produced by the workflow}
package=org.syun.pokemonw2.standalone
platform_tools="${ANDROID_HOME:?}/platform-tools"
adb="$platform_tools/adb"

"$adb" install -r "$apk"
"$adb" shell pm clear "$package"
"$adb" logcat -c
"$adb" shell am start -W -a android.intent.action.MAIN -c android.intent.category.LAUNCHER \
  -n "$package/org.syun.pokemonw2.StandaloneLauncherActivity"

# The missing-asset screen can only be drawn after AppCompat has applied the app theme.
# Reaching it verifies that a successful install didn't hide a crash on the first frame.
for attempt in {1..12}; do
  if "$adb" shell uiautomator dump /data/local/tmp/white2-window.xml >/dev/null 2>&1; then
    ui=$("$adb" exec-out cat /data/local/tmp/white2-window.xml)
    if [[ "$ui" == *"ゲームを起動できませんでした"* ]] && "$adb" shell pidof "$package"; then
      echo 'PASS: launcher installed, opened, and displayed the expected missing-asset message.'
      exit 0
    fi
  fi
  sleep 2
done
"$adb" logcat -b crash -d
exit 1
