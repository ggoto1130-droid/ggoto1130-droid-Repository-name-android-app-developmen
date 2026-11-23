#!/usr/bin/env python3
"""Apply the standalone launcher overlay to a clean melonDS Android checkout."""

from pathlib import Path
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
import hashlib

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(os.environ.get("MELONDS_SOURCE_DIR", "melonDS-android"))
ANDROID = "http://schemas.android.com/apk/res/android"
TOOLS = "http://schemas.android.com/tools"
ET.register_namespace("android", ANDROID)
ET.register_namespace("tools", TOOLS)


def android(name: str) -> str:
    return f"{{{ANDROID}}}{name}"


def main() -> None:
    manifest = UPSTREAM / "app/src/main/AndroidManifest.xml"
    app_gradle = UPSTREAM / "app/build.gradle.kts"
    strings = UPSTREAM / "app/src/main/res/values/strings.xml"
    app_config = UPSTREAM / "buildSrc/src/main/kotlin/AppConfig.kt"
    if not manifest.is_file() or not app_gradle.is_file() or not strings.is_file() or not app_config.is_file():
        raise SystemExit(f"Not a melonDS Android source checkout: {UPSTREAM}")

    tree = ET.parse(manifest)
    root = tree.getroot()
    application = root.find("application")
    if application is None:
        raise SystemExit("AndroidManifest.xml has no application element")

    for activity in list(application.findall("activity")):
        name = activity.get(android("name"), "")
        if name in (".ui.romlist.RomListActivity", "me.magnum.melonds.ui.romlist.RomListActivity"):
            for intent_filter in list(activity.findall("intent-filter")):
                actions = {node.get(android("name")) for node in intent_filter.findall("action")}
                categories = {node.get(android("name")) for node in intent_filter.findall("category")}
                if "android.intent.action.MAIN" in actions and "android.intent.category.LAUNCHER" in categories:
                    activity.remove(intent_filter)
            activity.set(android("exported"), "false")

    for activity in list(application.findall("activity")):
        if activity.get(android("name")) == "org.syun.pokemonw2.StandaloneLauncherActivity":
            application.remove(activity)
    launcher = ET.SubElement(application, "activity", {
        android("name"): "org.syun.pokemonw2.StandaloneLauncherActivity",
        android("theme"): "@style/SplashTheme",
        android("exported"): "true",
    })
    intent_filter = ET.SubElement(launcher, "intent-filter")
    ET.SubElement(intent_filter, "action", {android("name"): "android.intent.action.MAIN"})
    ET.SubElement(intent_filter, "category", {android("name"): "android.intent.category.LAUNCHER"})

    for provider in list(application.findall("provider")):
        if provider.get(android("name")) == "org.syun.pokemonw2.GameProvider":
            application.remove(provider)
    ET.SubElement(application, "provider", {
        android("name"): "org.syun.pokemonw2.GameProvider",
        android("authorities"): "${applicationId}.game",
        android("exported"): "false",
        android("grantUriPermissions"): "true",
    })

    ET.indent(tree, space="    ")
    tree.write(manifest, encoding="utf-8", xml_declaration=True)
    with manifest.open("a", encoding="utf-8") as output:
        output.write("\n")

    gradle = app_gradle.read_text(encoding="utf-8")
    gradle, changed_id = re.subn(r'applicationId\s*=\s*"[^"]+"', 'applicationId = "org.syun.pokemonw2.standalone"', gradle, count=1)
    gradle, changed_version_code = re.subn(r'versionCode\s*=\s*AppConfig\.versionCode', 'versionCode = 1', gradle, count=1)
    gradle, changed_version_name = re.subn(r'versionName\s*=\s*AppConfig\.versionName', 'versionName = "1.0.0"', gradle, count=1)
    if (changed_id, changed_version_code, changed_version_name) != (1, 1, 1):
        raise SystemExit("Could not safely update the application ID and version")
    app_gradle.write_text(gradle, encoding="utf-8")

    strings_xml = strings.read_text(encoding="utf-8")
    strings_xml, changed_label = re.subn(
        r'(<string\s+name="app_name"[^>]*>).*?(</string>)',
        r'\1ポケモン ホワイト2\2',
        strings_xml,
        count=1,
        flags=re.DOTALL,
    )
    if changed_label != 1:
        raise SystemExit("Could not find the app_name resource")
    strings.write_text(strings_xml, encoding="utf-8")

    config = app_config.read_text(encoding="utf-8")
    config, changed_sdk = re.subn(r'const val compileSdkVersion = \d+', 'const val compileSdkVersion = 36', config, count=1)
    if changed_sdk != 1:
        raise SystemExit("Could not safely set the supported Android 16 SDK level")
    app_config.write_text(config, encoding="utf-8")

    source_overlay = ROOT / "overlay/app/src/main/java/org/syun/pokemonw2"
    source_target = UPSTREAM / "app/src/main/java/org/syun/pokemonw2"
    shutil.copytree(source_overlay, source_target, dirs_exist_ok=True)

    rom_path = os.environ.get("POKEMON_ROM_PATH")
    if rom_path:
        rom = Path(rom_path)
        if not rom.is_file():
            raise SystemExit(f"POKEMON_ROM_PATH does not exist: {rom}")
        expected_size = 536_870_912
        expected_hash = "3b3f91fe0e4cc323ea73a1d6242fa04b255d98c4e44971594624bad919713a7b"
        if rom.stat().st_size != expected_size:
            raise SystemExit(f"The NDS image must be {expected_size} bytes")
        digest = hashlib.sha256()
        with rom.open("rb") as source:
            header = source.read(16)
            if header[:10] != b"POKEMON W2" or header[12:16] != b"IRDO":
                raise SystemExit("The NDS image is not Pokémon White 2 (IRDO)")
            source.seek(0)
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected_hash:
            raise SystemExit("The NDS image SHA-256 does not match the verified build input")
        asset_target = UPSTREAM / "app/src/main/assets/bundled/pokemon_white2.nds"
        asset_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rom, asset_target)
        print("Added user-provided game image to this private build workspace.")
    elif os.environ.get("ALLOW_MISSING_ROM") == "1":
        print("Building a source-check APK without a game image; it is not playable.")
    else:
        raise SystemExit("Set POKEMON_ROM_PATH to the private game image. The ROM is never added to this repository.")


if __name__ == "__main__":
    main()
