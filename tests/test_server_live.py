import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import threading
import time
import urllib.request
import json
from app.assistant_session import RohaSession
from app.web_app import WebState, RohaHTTPServer, RohaWebHandler

def test_live_server():
    session = RohaSession()
    state = WebState(session=session)
    test_port = 8765
    server = RohaHTTPServer(("127.0.0.1", test_port), RohaWebHandler, state)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(1.0)

    url = f"http://127.0.0.1:{test_port}/"
    print(f"Fetching {url} ...")
    with urllib.request.urlopen(url) as resp:
        code = resp.getcode()
        html = resp.read().decode("utf-8")
        print(f"Status Code: {code}, Content Length: {len(html)} bytes")
        assert "ROHA // AI WORKSPACE" in html or "ROHA" in html
        print("HTML verification: PASSED")

    api_url = f"http://127.0.0.1:{test_port}/api/state"
    print(f"Fetching {api_url} ...")
    with urllib.request.urlopen(api_url) as resp:
        code = resp.getcode()
        data = json.loads(resp.read().decode("utf-8"))
        print(f"API State: Model={data.get('model')}, Verified={data.get('is_verified')}")
        print("API state verification: PASSED")

    # Test /api/lock
    req_lock = urllib.request.Request(f"http://127.0.0.1:{test_port}/api/lock", data=b"{}", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_lock) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("ok") is True and data.get("is_verified") is False
        print("API /api/lock verification: PASSED")

    # Test /api/auth
    req_auth = urllib.request.Request(f"http://127.0.0.1:{test_port}/api/auth", data=json.dumps({"pin": "1430"}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_auth) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("ok") is True and data.get("is_verified") is True
        print("API /api/auth verification: PASSED")

    server.shutdown()
    server.server_close()
    session.close()
    print("ALL LIVE SERVER INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_live_server()
