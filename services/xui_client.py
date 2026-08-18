import logging
import time
import uuid
from typing import Dict, List, Optional
import aiohttp

logger = logging.getLogger(__name__)


class XUIClient:
    def __init__(self, base_url: str, username: str, password: str, api_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.api_token = api_token
        self._session = None

    async def _get_session(self):
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            headers = {}
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            self._session = aiohttp.ClientSession(
                connector=connector, headers=headers
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def login(self):
        if self.api_token:
            return True
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/login",
                data={"username": self.username, "password": self.password}
            ) as resp:
                result = await resp.json(content_type=None)
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
        return settings.get("clients", [])

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

    async def add_client(self, inbound_id, email, traffic_gb=0, expire_days=0, tg_id=0):
        import json as _json
        client_id = str(uuid.uuid4())
        inbounds = await self.get_inbounds()
        inbound = next((i for i in inbounds if i["id"] == inbound_id), None)
        stream_raw = (inbound or {}).get("streamSettings", "{}")
        stream = _json.loads(stream_raw) if isinstance(stream_raw, str) else stream_raw
        security = stream.get("security", "")
        flow = "xtls-rprx-vision" if security == "reality" else ""
        payload = {
            "inboundIds": [inbound_id],
            "client": {
                "id": client_id,
                "email": email,
                "enable": True,
                "expiryTime": int((time.time() + expire_days * 86400) * 1000) if expire_days else 0,
                "totalGB": traffic_gb * 1024**3 if traffic_gb else 0,
                "limitIp": 0,
                "flow": flow,
                "subId": "",
                "tgId": int(tg_id) if tg_id else 0
            }
        }
        result = await self._request("POST", "/panel/api/clients/add", json=payload)
        return client_id if result and result.get("success") else None

    async def update_client(self, inbound_id, client_uuid, **fields):
        clients = await self.get_clients(inbound_id)
        client = next((c for c in clients if c.get("id") == client_uuid), {})
        email = client.get("email", "")
        payload = {
            "id": client_uuid,
            "email": email,
            "enable": client.get("enable", True),
            "expiryTime": client.get("expiryTime", 0),
            "totalGB": client.get("totalGB", 0),
            "limitIp": client.get("limitIp", 0),
            "flow": client.get("flow", ""),
            "subId": client.get("subId", ""),
            "tgId": int(client.get("tgId", 0)) if client.get("tgId") else 0,
            **fields
        }
        result = await self._request("POST", f"/panel/api/clients/update/{email}", json=payload)
        return bool(result and result.get("success"))

    async def delete_client(self, inbound_id, client_uuid):
        clients = await self.get_clients(inbound_id)
        client = next((c for c in clients if c.get("id") == client_uuid), None)
        email = client.get("email") if client else client_uuid
        result = await self._request("POST", f"/panel/api/clients/del/{email}")
        return bool(result and result.get("success"))

    async def toggle_client(self, inbound_id, client_uuid, enable):
        return await self.update_client(inbound_id, client_uuid, enable=enable)

    async def reset_client_traffic(self, inbound_id, email):
        result = await self._request("POST", f"/panel/api/clients/resetTraffic/{email}")
        return bool(result and result.get("success"))

    async def get_client_link(self, inbound_id, client_uuid):
        import json, base64
        inbounds = await self.get_inbounds()
        inbound = next((i for i in inbounds if i["id"] == inbound_id), None)
        if not inbound:
            return None
        protocol = inbound.get("protocol", "").lower()
        address = self.base_url.split("//")[-1].split(":")[0]
        port = inbound.get("port", 443)
        stream_raw = inbound.get("streamSettings", "{}")
        stream = json.loads(stream_raw) if isinstance(stream_raw, str) else stream_raw
        network = stream.get("network", "tcp")
        security = stream.get("security", "none")
        if protocol == "vless":
            params = f"type={network}&security={security}&encryption=none"
            if security == "reality":
                reality = stream.get("realitySettings", {})
                rs = reality.get("settings", {})
                pbk = rs.get("publicKey", "")
                fp  = rs.get("fingerprint", "chrome")
                sni = rs.get("serverName", "") or (reality.get("serverNames", [""])[0])
                sid = (reality.get("shortIds", [""])[-1])
                params += f"&pbk={pbk}&fp={fp}&sni={sni}&sid={sid}&spx=%2F"
            settings_raw = inbound.get("settings", "{}")
            settings = json.loads(settings_raw) if isinstance(settings_raw, str) else settings_raw
            clients = settings.get("clients", [])
            client_obj = next((c for c in clients if c.get("id") == client_uuid), {})
            flow = client_obj.get("flow", "")
            if flow:
                params += f"&flow={flow}"
            remark = inbound.get("remark", "VPN")
            email = client_obj.get("email", "")
            return f"vless://{client_uuid}@{address}:{port}?{params}#{remark}-{email}"
        elif protocol == "vmess":
            cfg = {"v":"2","ps":inbound.get("remark","VPN"),"add":address,"port":str(port),"id":client_uuid,"aid":"0","net":network,"type":"none","tls":security}
            return f"vmess://{base64.b64encode(json.dumps(cfg).encode()).decode()}"
        return None
