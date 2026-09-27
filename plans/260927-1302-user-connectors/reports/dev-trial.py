"""Dev trial: ask the agent real questions that use connectors, answer approval
cards by plan, and write everything to trial-log.json for grading."""

import asyncio
import json
import sys
import uuid
from pathlib import Path

import httpx

API = "http://localhost:8002/api/v1"
SP = Path(__file__).parent
PASSWORD = (SP / "trial-password").read_text().strip()


async def login(client, email):
    r = await client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    return {"authorization": f"Bearer {r.json()['access_token']}"}


async def ask(client, headers, thread_id, text, plan, log, *, peer_headers=None):
    turn_id = str(uuid.uuid4())
    r = await client.post(
        f"{API}/threads/{thread_id}/turns",
        headers=headers,
        json={"turn_id": turn_id, "text": text, "client_capabilities": ["approvals"]},
    )
    r.raise_for_status()
    events, cards, answers = [], [], []
    async with client.stream("GET", f"{API}/turns/{turn_id}/events", headers=headers, timeout=None) as stream:
        kind = None
        async for line in stream.aiter_lines():
            if line.startswith("event:"):
                kind = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
                events.append(data)
                typ = data.get("type") or kind
                if typ == "approval.requested":
                    card = data["data"]
                    cards.append(card)
                    decision = plan.get(card["tool"], plan.get("*", "allow_once"))
                    if peer_headers is not None:
                        stolen = await client.post(
                            f"{API}/turns/{turn_id}/approvals/{card['call_id']}",
                            headers=peer_headers,
                            json={"decision": "allow_once"},
                        )
                        answers.append({"peer_attempt": stolen.status_code})
                    reply = await client.post(
                        f"{API}/turns/{turn_id}/approvals/{card['call_id']}",
                        headers=headers,
                        json={"decision": decision},
                    )
                    answers.append({"tool": card["tool"], "decision": decision, "status": reply.status_code})
                if typ in ("turn.completed", "turn.incomplete", "turn.failed", "turn.cancelled"):
                    break
    turn = (await client.get(f"{API}/turns/{turn_id}", headers=headers)).json()
    detail = (await client.get(f"{API}/threads/{thread_id}", headers=headers)).json()
    message = detail["messages"][-1] if detail.get("messages") else {}
    entry = {
        "question": text,
        "turn_id": turn_id,
        "status": turn.get("status"),
        "terminal_reason": turn.get("terminal_reason"),
        "cards": cards,
        "answers": answers,
        "tool_calls": [
            {k: call.get(k) for k in ("name", "status", "summary", "error")}
            for call in (message.get("content", {}).get("tool_calls") or [])
        ],
        "text": message.get("content", {}).get("text"),
    }
    log.append(entry)
    print(json.dumps({k: entry[k] for k in ("turn_id", "status", "answers")}, ensure_ascii=False), flush=True)
    return entry


async def paced(*args, **kwargs):
    for attempt in range(3):
        await asyncio.sleep(45)
        entry = await ask(*args, **kwargs)
        if entry["terminal_reason"] != "gateway_timeout":
            return entry
        print("route throttled; waiting before asking again", flush=True)
        await asyncio.sleep(60)
    return entry


async def main():
    log = []
    async with httpx.AsyncClient(timeout=60) as client:
        alice = await login(client, "connector-trial-a@example.com")
        bob = await login(client, "connector-trial-b@example.com")
        existing = {c["name"] for c in (await client.get(f"{API}/connectors", headers=alice)).json()["connectors"]}
        for name, url in (("Context7", "https://mcp.context7.com/mcp"), ("DeepWiki", "https://mcp.deepwiki.com/mcp")):
            if name not in existing:
                r = await client.post(f"{API}/connectors", headers=alice, json={"name": name, "url": url})
                print(name, r.status_code, flush=True)
        mine = (await client.get(f"{API}/connectors", headers=alice)).json()["connectors"]
        by_name = {c["name"]: c for c in mine}
        ctx7 = by_name["Context7"]
        # query-docs: allow; resolve-library-id: stays "ask" to exercise the card.
        await client.put(f"{API}/connectors/{ctx7['id']}/tools/query-docs", headers=alice, json={"action": "allow"})
        log.append({"setup": {c["name"]: [(t["name"], t["effect"], t["action"]) for t in c["tools"]] for c in (await client.get(f"{API}/connectors", headers=alice)).json()["connectors"]}})
        log.append({"bob_sees": (await client.get(f"{API}/connectors", headers=bob)).json()["connectors"]})

        thread = (await client.post(f"{API}/threads", headers=alice, json={})).json()["id"]
        await client.put(f"{API}/connectors/preferences", headers=alice, json={"tool_access": "on_demand"})
        await paced(client, alice, thread,
                  "Dùng kết nối Context7 tra tài liệu thư viện Python vnstock: hàm hoặc phương thức nào dùng để lấy báo cáo tài chính (bảng cân đối, kết quả kinh doanh)? Trả lời ngắn, kèm tên hàm.",
                  {"resolve-library-id": "allow_once"}, log, peer_headers=bob)
        await client.put(f"{API}/connectors/preferences", headers=alice, json={"tool_access": "preloaded"})
        await paced(client, alice, thread,
                  "Dùng DeepWiki đọc cấu trúc wiki của repo GitHub thinh-vu/vnstock và liệt kê các phần chính.",
                  {"*": "allow_once"}, log)
        await paced(client, alice, thread,
                  "Dùng DeepWiki đọc nội dung wiki của repo pandas-dev/pandas và cho biết rolling window là gì.",
                  {"*": "deny"}, log)
        await paced(client, alice, thread,
                  "Giá đóng cửa gần nhất của VNM là bao nhiêu? Rồi dùng Context7 tra tài liệu vnstock xem hàm nào lấy giá lịch sử theo ngày.",
                  {"resolve-library-id": "always"}, log)
        await paced(client, alice, thread,
                  "Theo wiki DeepWiki của repo thinh-vu/vnstock, gói miễn phí (guest) được gọi tối đa bao nhiêu lần mỗi phút? Nêu con số.",
                  {"*": "allow_once"}, log)
        bthread = (await client.post(f"{API}/threads", headers=bob, json={})).json()["id"]
        await paced(client, bob, bthread,
                  "Dùng kết nối Context7 tra tài liệu thư viện vnstock: hàm nào lấy báo cáo tài chính?",
                  {}, log)
        log.append({"final_connectors": (await client.get(f"{API}/connectors", headers=alice)).json()["connectors"]})
    (SP / "trial-log-run2.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))


asyncio.run(main())
