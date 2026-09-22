"""
Run this standalone (NOT through the GUI) whenever you need a fresh PoToken.

Steps to get the values it asks for:
1. Open a browser and go to an embedded/logged-out YouTube video,
   e.g. https://www.youtube.com/embed/aqz-KE-bpKQ
   Make sure you are NOT logged in to any account.
2. Open developer console (F12) -> Network tab -> filter by "v1/player"
3. Click play so a player request appears in the Network tab
4. In that request's payload JSON, find:
      serviceIntegrityDimensions.poToken   -> PoToken
      context.client.visitorData           -> visitorData
5. Paste them in when this script asks.

This caches them to po_token_cache.json so download.py can reuse them
without ever prompting for input (which would crash the GUI thread).
"""

import json
from pytubefix import YouTube

CACHE_FILE = "po_token_cache.json"


def main():
    po_token = input("Paste PoToken: ").strip()
    visitor_data = input("Paste visitorData: ").strip()

    with open(CACHE_FILE, "w") as f:
        json.dump({"po_token": po_token, "visitor_data": visitor_data}, f)

    print(f"Saved to {CACHE_FILE}. Testing it now...")

    yt = YouTube(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        use_po_token=True,
        po_token_verifier=lambda: (visitor_data, po_token),
    )
    print(f"Success — got title: {yt.title}")


if __name__ == "__main__":
    main()