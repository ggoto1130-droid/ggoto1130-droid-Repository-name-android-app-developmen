"""Exercise a privately supplied release. Only encrypted screenshots leave the runner."""
from pathlib import Path
import hashlib
import io
import json
import os
import subprocess as sp
import time
import urllib.request
import zipfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

tmp = Path(os.environ["RUNNER_TEMP"])
package = "org.syun.pokemonw2.standalone"
sha = "12ac74795a9595f44874c0ae3f0c7a75e83335e59f8bf73fde80339aedb9c95b"
def command(*args, **kw):
    return sp.run(args, capture_output=True, timeout=120, **kw)
def adb(*args):
    result = command("adb", *args, check=True)
    return result.stdout

def payload():
    ref = "refs/heads/codex/pokemon-white2-qa-input"
    for _ in range(125):
        fetch = command("git", "fetch", "-q", "--depth=1", "origin", ref)
        if fetch.returncode == 0:
            sealed = command("git", "show", "FETCH_HEAD:input/" + os.environ["GITHUB_RUN_ID"] + ".b64")
            if sealed.returncode == 0:
                import base64
                data = base64.b64decode(sealed.stdout, validate=False)
                box = command("openssl", "cms", "-decrypt", "-binary", "-inform", "DER",
                              "-recip", str(tmp / "recipient.pem"), "-inkey", str(tmp / "recipient.key"),
                              input=data, check=True)
                return json.loads(box.stdout)
        time.sleep(3)
    raise RuntimeError("No sealed input for this run")

def test():
    inputs = payload()
    key = bytes.fromhex(inputs["key"])
    from urllib.parse import urlparse
    parts = []
    for url in inputs["urls"]:
        host = urlparse(url).hostname or ""
        if urlparse(url).scheme != "https" or not host.endswith((".oaiusercontent.com", ".blob.core.windows.net", ".amazonaws.com")):
            raise RuntimeError("Invalid stage host")
        try:
            with urllib.request.urlopen(url, timeout=120) as stream:
                parts.append(stream.read(104000000))
        except Exception:
            raise RuntimeError("Temporary delivery could not be retrieved") from None
    encrypted = b"".join(parts)
    del parts
    aes = AESGCM(key)
    apk = aes.decrypt(encrypted[:12], encrypted[12:], b"apk-1.0.2")
    if hashlib.sha256(apk).hexdigest() != sha:
        raise RuntimeError("Release checksum mismatch")
    local = tmp / "signed.apk"
    local.write_bytes(apk)
    del apk, encrypted
    print("PASS identical signed release SHA-256 " + sha, flush=True)
    notes = []
    frames = io.BytesIO()
    try:
        print(adb("install", "-r", str(local)).decode().strip(), flush=True)
        adb("shell","wm","size","320x640")
        adb("shell","settings","put","secure","immersive_mode_confirmations","confirmed")
        component = package + "/org.syun.pokemonw2.StandaloneLauncherActivity"
        def launch():
            return adb("shell","am","start","-W","-a","android.intent.action.MAIN","-c","android.intent.category.LAUNCHER","-n",component).decode()
        with zipfile.ZipFile(frames,"w",compression=zipfile.ZIP_STORED) as z:
            notes.append(launch())
            for i in range(48):
                z.writestr(f"first-{i:02}.png",adb("exec-out","screencap","-p"))
                if i in (9,12,15,18,21,24,27,30,33,36,40,44):
                    adb("shell","input","tap","294","570")
                if i in (7,15,28,44):
                    print("Captured gameplay interval " + str(i), flush=True)
                time.sleep(1.6)
            adb("shell","am","force-stop",package)
            notes.append(launch())
            for i in range(16):
                z.writestr(f"second-{i:02}.png",adb("exec-out","screencap","-p"))
                if i in (6,9,12):
                    adb("shell","input","tap","294","570")
                time.sleep(1.4)
            notes.append(adb("shell","pidof",package).decode())
            notes.append(adb("shell","run-as",package,"ls","-l","files").decode())
            notes.append(adb("logcat","-b","crash","-d").decode(errors="replace"))
            z.writestr("device.txt","\n".join(notes))
    finally:
        nonce = os.urandom(12)
        (tmp/"evidence.sealed").write_bytes(nonce+aes.encrypt(nonce,frames.getvalue(),b"device-evidence"))
        local.unlink(missing_ok=True)
if __name__ == "__main__":
    test()
