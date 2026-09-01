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

    # Test /api/memories GET
    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/memories") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert "memories" in data
        print("API /api/memories GET verification: PASSED")

    # Test /api/memories/graph GET
    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/memories/graph") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert "nodes" in data and "links" in data
        print("API /api/memories/graph GET verification: PASSED")

    # Test /api/memories/playground POST
    req_pg = urllib.request.Request(f"http://127.0.0.1:{test_port}/api/memories/playground", data=json.dumps({"query": "test query"}).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req_pg) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert "semantic_matches" in data and "episodic_matches" in data
        print("API /api/memories/playground POST verification: PASSED")

    # Test /api/workspace/tree GET
    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/workspace/tree") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("ok") is True and "tree" in data
        print("API /api/workspace/tree GET verification: PASSED")

    # Test /api/workspace/file GET
    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/workspace/file?path=run.py") as resp:
        data = json.loads(resp.read().decode("utf-8"))
        assert data.get("ok") is True and "content" in data
        print("API /api/workspace/file GET verification: PASSED")

    server.shutdown()
    server.server_close()
    session.close()
    print("ALL LIVE SERVER INTEGRATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_live_server()
