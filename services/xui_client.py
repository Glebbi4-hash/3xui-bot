import logging
import time
import uuid
from typing import Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)

class XUIClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(cookie_jar=jar, connector=connector)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self):
        session = await self._get_session()
        try:
            async with session.post(f"{self.base_url}/login", data={"username": self.username, "password": self.password}) as resp:
                result = await resp.json()
                if result.get("success"):
                    logger.info("3x-ui login successful")
                    return True
                logger.error("3x-ui login failed: %s", result)
                return False
        except Exception as exc:
            logger.exception("3x-ui login error: %s", exc)
            return False

    async def _request(self, method, path, **kwargs):
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        try:
            async with session.request(method, url, allow_redirects=True, **kwargs) as resp:
                if resp.status == 401:
                    if await self.login():
                        async with session.request(method, url, allow_redirects=True, **kwargs) as r2:
                            return await r2.json(content_type=None)
                    return None
                return await resp.json(content_type=None)
        except Exception as exc:
            logger.exception("request error [%s %s]: %s", method, path, exc)
            return None

    async def get_inbounds(self):
        result = await self._request("GET", "/panel/api/inbounds/list")
        return result.get("obj", []) if result and result.get("success") else []

    async def get_inbound(self, inbound_id):
        result = await self._request("GET", f"/panel/api/inbounds/get/{inbound_id}")
        return result.get("obj") if result and result.get("success") else None

    async def get_clients(self, inbound_id):
        import json
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return []
        settings_raw = inbound.get("settings", "{}")
        try:
            settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
        except Exception:
            return []
        clients = settings.get("clients", [])
        # Merge with clientStats for enable status
        stats = {s["email"]: s for s in inbound.get("clientStats") or []}
        for c in clients:
            email = c.get("email", "")
            if email in stats:
                c["enable"] = stats[email].get("enable", c.get("enable", True))
        return clients

    async def get_client_traffics(self, inbound_id):
        inbounds = await self.get_inbounds()
        inbound = next((i for i in inbounds if i["id"] == inbound_id), None)
        if not inbound:
            return {}
        stats = inbound.get("clientStats") or []
        result = {}
        for s in stats:
            if "email" in s:
                result[s["email"]] = s
            if "uuid" in s:
                result[s["uuid"]] = s
        return result

    async def add_client(self, inbound_id, email, traffic_gb=0, expire_days=0):
        import json as _json
        client_id = str(uuid.uuid4())
        # Get inbound to detect flow type
        inbounds = await self.get_inbounds()
        inbound = next((i for i in inbounds if i["id"] == inbound_id), None)
        stream_raw = (inbound or {}).get("streamSettings", "{}")
        stream = _json.loads(stream_raw) if isinstance(stream_raw, str) else stream_raw
        security = stream.get("security", "")
        flow = "xtls-rprx-vision" if security == "reality" else ""
        payload = {
            "id": inbound_id,
            "settings": _json.dumps({"clients": [{
                "id": client_id,
                "email": email,
                "enable": True,
                "expiryTime": int((time.time() + expire_days * 86400) * 1000) if expire_days else 0,
                "totalGB": traffic_gb * 1024**3 if traffic_gb else 0,
                "limitIp": 0,
                "flow": flow,
                "subId": "",
                "tgId": ""
            }]})
        }
        result = await self._request("POST", "/panel/api/inbounds/addClient", json=payload)
        return client_id if result and result.get("success") else None

    async def update_client(self, inbound_id, client_uuid, **fields):
        payload = {"id": inbound_id, "settings": {"clients": [{"id": client_uuid, **fields}]}}
        result = await self._request("POST", f"/panel/api/inbounds/updateClient/{client_uuid}", json=payload)
        return bool(result and result.get("success"))

    async def delete_client(self, inbound_id, client_uuid):
        result = await self._request("POST", f"/panel/api/inbounds/{inbound_id}/delClient/{client_uuid}")
        return bool(result and result.get("success"))

    async def toggle_client(self, inbound_id, client_uuid, enable):
        return await self.update_client(inbound_id, client_uuid, enable=enable)

    async def reset_client_traffic(self, inbound_id, email):
        result = await self._request("POST", f"/panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}")
        return bool(result and result.get("success"))

    async def get_client_link(self, inbound_id, client_uuid):
        inbound = await self.get_inbound(inbound_id)
        if not inbound:
            return None
        import json, base64
        protocol = inbound.get("protocol", "").lower()
        address = self.base_url.split("//")[-1].split(":")[0]
        port = inbound.get("port", 443)
        stream_raw = inbound.get("streamSettings", "{}")
        stream = json.loads(stream_raw) if isinstance(stream_raw, str) else stream_raw
        network = stream.get("network", "tcp")
        security = stream.get("security", "none")
        if protocol == "vless":
            return f"vless://{client_uuid}@{address}:{port}?type={network}&security={security}#{inbound.get(chr(114)+chr(101)+chr(109)+chr(97)+chr(114)+chr(107), 'VPN')}"
        elif protocol == "vmess":
            cfg = {"v":"2","ps":inbound.get("remark","VPN"),"add":address,"port":str(port),"id":client_uuid,"aid":"0","net":network,"type":"none","tls":security}
            return f"vmess://{base64.b64encode(json.dumps(cfg).encode()).decode()}"
        return None
