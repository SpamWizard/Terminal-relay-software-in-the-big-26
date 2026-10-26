"""Fake iwlist for the desk terminal. Usage: iwlist [iface] scanning"""

from __future__ import annotations

import base64
import sys

# Scan payload kept encoded so `cat`/`grep` on this file is not the solve.
_PAYLOAD = (
    "d2xhbjAgICAgIFNjYW4gY29tcGxldGVkIDoKICAgICAgICAgIENlbGwgMDEgLSBBZGRy"
    "ZXNzOiBBQTpBQTpBQTpBQTpBQTowMQogICAgICAgICAgICAgICAgICBFU1NJRDoiRnJl"
    "ZUFpcnBvcnRXaUZpIgogICAgICAgICAgICAgICAgICBRdWFsaXR5PTIwLzcwICBTaWdu"
    "YWwgbGV2ZWw9LTcwIGRCbQogICAgICAgICAgQ2VsbCAwMiAtIEFkZHJlc3M6IEFBOkFB"
    "OkFBOkFBOkFBOjAyCiAgICAgICAgICAgICAgICAgIEVTU0lEOiJ4ZmluaXR5d2lmaSIK"
    "ICAgICAgICAgICAgICAgICAgUXVhbGl0eT0xOC83MCAgU2lnbmFsIGxldmVsPS03MiBk"
    "Qm0KICAgICAgICAgIENlbGwgMDMgLSBBZGRyZXNzOiBBQTpBQTpBQTpBQTpBQTowMwog"
    "ICAgICAgICAgICAgICAgICBFU1NJRDoiQW5kcm9pZEFQXzg4MjEiCiAgICAgICAgICAg"
    "ICAgICAgIFF1YWxpdHk9MTIvNzAgIFNpZ25hbCBsZXZlbD0tODAgZEJtCiAgICAgICAg"
    "ICBDZWxsIDA0IC0gQWRkcmVzczogQUE6QUE6QUE6QUE6QUE6MDQKICAgICAgICAgICAg"
    "ICAgICAgRVNTSUQ6IlNhaW50Y29uR3Vlc3QiCiAgICAgICAgICAgICAgICAgIFF1YWxp"
    "dHk9NTUvNzAgIFNpZ25hbCBsZXZlbD0tNDUgZEJtCiAgICAgICAgICBDZWxsIDA1IC0g"
    "QWRkcmVzczogQUE6QUE6QUE6QUE6QUE6MDUKICAgICAgICAgICAgICAgICAgRVNTSUQ6"
    "IlNhaW50Y29uU3RhZmYtRG9Ob3RVc2UiCiAgICAgICAgICAgICAgICAgIFF1YWxpdHk9"
    "NDAvNzAgIFNpZ25hbCBsZXZlbD0tNTUgZEJtCiAgICAgICAgICBDZWxsIDA2IC0gQWRk"
    "cmVzczogQUE6QUE6QUE6QUE6QUE6MDYKICAgICAgICAgICAgICAgICAgRVNTSUQ6IkhQ"
    "LVByaW50LTQyIgogICAgICAgICAgICAgICAgICBRdWFsaXR5PTEwLzcwICBTaWduYWwg"
    "bGV2ZWw9LTgyIGRCbQo="
)


def main(argv: list[str]) -> int:
    joined = " ".join(argv).casefold()
    if argv and not any(tok in joined for tok in ("scan", "scanning")):
        print("iwlist: unknown command (try: iwlist wlan0 scanning)", file=sys.stderr)
        return 1
    print(base64.b64decode(_PAYLOAD).decode("ascii"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
