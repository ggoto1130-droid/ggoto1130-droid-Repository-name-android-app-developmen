#!/usr/bin/env bash
set -euo pipefail

REPOSITORY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM_DIR="${MELONDS_SOURCE_DIR:-$REPOSITORY_ROOT/melonDS-android}"
UPSTREAM_COMMIT="909647ba95ce903797e0112fedae570732bfd9cc"

if [[ -z "${POKEMON_ROM_PATH:-}" ]]; then
  echo "Set POKEMON_ROM_PATH to the private White 2 NDS image." >&2
  exit 1
fi
if [[ -z "${POKEMON_KEYSTORE:-}" || -z "${POKEMON_KEYSTORE_PASSWORD:-}" || -z "${POKEMON_KEY_ALIAS:-}" || -z "${POKEMON_KEY_PASSWORD:-}" ]]; then
  echo "Set POKEMON_KEYSTORE, POKEMON_KEYSTORE_PASSWORD, POKEMON_KEY_ALIAS, and POKEMON_KEY_PASSWORD for a stable signed release." >&2
  exit 1
fi

if [[ ! -d "$UPSTREAM_DIR/.git" ]]; then
  git clone --recurse-submodules https://github.com/rafaelvcaetano/melonDS-android.git "$UPSTREAM_DIR"
fi

git -C "$UPSTREAM_DIR" fetch --recurse-submodules origin "$UPSTREAM_COMMIT"
git -C "$UPSTREAM_DIR" checkout --detach "$UPSTREAM_COMMIT"
git -C "$UPSTREAM_DIR" submodule update --init --recursive

MELONDS_SOURCE_DIR="$UPSTREAM_DIR" python3 "$REPOSITORY_ROOT/scripts/apply_overlay.py"

POKEMON_KEYSTORE="$POKEMON_KEYSTORE" \
POKEMON_KEYSTORE_PASSWORD="$POKEMON_KEYSTORE_PASSWORD" \
POKEMON_KEY_ALIAS="$POKEMON_KEY_ALIAS" \
POKEMON_KEY_PASSWORD="$POKEMON_KEY_PASSWORD" \
python3 - <<'PY'
import os
from pathlib import Path

def prop(value: str) -> str:
    return value.replace("\\", "\\\\").replace(":", "\\:").replace("=", "\\=")

path = Path("local.properties")
path.write_text(
    "\n".join((
        f"MELONDS_KEYSTORE={prop(os.environ['POKEMON_KEYSTORE'])}",
        f"MELONDS_KEYSTORE_PASSWORD={prop(os.environ['POKEMON_KEYSTORE_PASSWORD'])}",
        f"MELONDS_KEY_ALIAS={prop(os.environ['POKEMON_KEY_ALIAS'])}",
        f"MELONDS_KEY_PASSWORD={prop(os.environ['POKEMON_KEY_PASSWORD'])}",
        "",
    )),
    encoding="utf-8",
)
PY

cd "$UPSTREAM_DIR"
bash ./gradlew :app:assembleGitHubProdRelease

APK_PATH="$UPSTREAM_DIR/app/build/outputs/apk/gitHubProd/release/app-gitHubProd-release.apk"
if [[ ! -s "$APK_PATH" ]]; then
  echo "Gradle did not create the expected release APK: $APK_PATH" >&2
  exit 1
fi
printf 'APK: %s\n' "$APK_PATH"
stat --printf='Size: %s bytes\n' "$APK_PATH"
