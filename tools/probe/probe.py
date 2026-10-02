"""Probe candidate data endpoints and print what each one actually returns."""
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request

UA = "costmodel-data-pipeline/0.1 (+https://github.com/GYZ001/costmodel)"


def probe(t):
    url = t["url"]
    data = None
    headers = {"User-Agent": t.get("ua", UA), "Accept": "*/*"}
    headers.update(t.get("headers", {}))
    if "json" in t:
        data = json.dumps(t["json"]).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=t.get("timeout", 60)) as r:
            body = r.read()
            status, final, ctype = r.status, r.geturl(), r.headers.get("Content-Type")
    except urllib.error.HTTPError as e:
        body = e.read() or b""
        status, final, ctype = e.code, url, e.headers.get("Content-Type")
    except Exception as e:  # noqa: BLE001 - probe reports every failure kind
        print(f"### {t['name']}\nURL: {url}\nERROR: {type(e).__name__}: {e}\n", flush=True)
        return
    dt = time.time() - t0
    print(f"### {t['name']}\nURL: {url}\nFINAL: {final}\nSTATUS: {status}  TYPE: {ctype}  BYTES: {len(body)}  "
          f"SHA256: {hashlib.sha256(body).hexdigest()[:16]}  TIME: {dt:.1f}s")
    if t.get("binary"):
        print(f"HEAD-HEX: {body[:16].hex()}")
    else:
        text = body.decode("utf-8", errors="replace")
        n = t.get("show", 1200)
        print(text[:n])
        if t.get("tail"):
            print("...TAIL...")
            print(text[-t["tail"]:])
        for needle in t.get("grep", []):
            idx, i = [], text.find(needle)
            while i != -1 and len(idx) < 5:
                idx.append(i)
                i = text.find(needle, i + 1)
            for i in idx:
                print(f"GREP[{needle}] ...{text[max(0, i - 200):i + 400]}...")
    print(flush=True)


def main():
    targets = json.load(open(sys.argv[1], encoding="utf-8"))
    for t in targets:
        probe(t)


if __name__ == "__main__":
    main()
