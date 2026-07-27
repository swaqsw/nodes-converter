#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nodes Converter — fetch proxy configs from GitLab, convert to v2rayN/Clash, integrate WARP."""

import json
import yaml
import re
import sys
import base64
from pathlib import Path
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

OUTPUT_DIR = Path("output")

GITLAB_SOURCES = {
    "clash.meta": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/clash.meta2/1/config.yaml",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/clash.meta2/1/config.yaml",
    ],
    "hysteria": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/hysteria/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/hysteria/1/config.json",
    ],
    "hysteria2": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/hysteria2/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/hysteria2/1/config.json",
    ],
    "singbox": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/singbox/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/singbox/1/config.json",
    ],
    "xray": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/xray/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/xray/1/config.json",
    ],
    "juicity": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/juicity/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/juicity/1/config.json",
    ],
}


def safe_float(val, default=0.0):
    """Parse bandwidth to float, handling '11 Mbps', '11 mbps', '55Mbps', etc."""
    if not val:
        return float(default)
    v = str(val).lower().replace("mbps", "").replace("mbps", "").strip()
    try:
        return float(v)
    except ValueError:
        return float(default)


def fetch(proto: str, urls: list[str]) -> str | None:
    for url in urls:
        try:
            r = requests.get(url, timeout=30, verify=False)
            r.raise_for_status()
            print(f"  [OK] {url[:60]}...")
            return r.text
        except Exception as e:
            print(f"  [FAIL] {url[:60]}... {e}")
    return None


# ---- Parsers ----

def parse_clash_meta(text: str) -> list[dict]:
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return []
    nodes = []
    for p in data.get("proxies", []) or []:
        if not isinstance(p, dict):
            continue
        nodes.append({
            "protocol": p.get("type", ""),
            "name": str(p.get("name", "")),
            "server": str(p.get("server", "")),
            "port": int(p.get("port", 0)),
            "auth": str(p.get("auth-str", p.get("password", "")) or ""),
            "sni": str(p.get("sni", "") or ""),
            "skip_cert_verify": bool(p.get("skip-cert-verify", False)),
            "alpn": p.get("alpn") or [],
            "up": str(p.get("up", "") or ""),
            "down": str(p.get("down", "") or ""),
        })
    return nodes


def parse_hysteria(text: str) -> list[dict]:
    data = json.loads(text)
    s = str(data.get("server", "") or "")
    if ":" in s:
        addr, port = s.rsplit(":", 1)
    else:
        addr, port = s, "0"
    return [{
        "protocol": "hysteria",
        "name": "hysteria-gitlab",
        "server": addr,
        "port": int(port) if port.isdigit() else 0,
        "auth": str(data.get("auth_str", "") or ""),
        "sni": str(data.get("server_name", "") or ""),
        "skip_cert_verify": bool(data.get("insecure", False)),
        "alpn": [data.get("alpn", "h3")],
        "up": str(data.get("up_mbps", "") or ""),
        "down": str(data.get("down_mbps", "") or ""),
    }]


def parse_hysteria2(text: str) -> list[dict]:
    data = json.loads(text)
    srv = str(data.get("server", "") or "")
    auth = str(data.get("auth", "") or "")
    tls = data.get("tls") or {}
    bw = data.get("bandwidth") or {}
    main_part = srv.split(",")[0].strip()
    if main_part.startswith("["):
        m = re.match(r"^\[(.+?)\]:(\d+)$", main_part)
        addr, port = (m.group(1), m.group(2)) if m else (main_part, "0")
    elif ":" in main_part:
        addr, port = main_part.rsplit(":", 1)
    else:
        addr, port = main_part, "0"
    return [{
        "protocol": "hysteria2",
        "name": "hysteria2-gitlab",
        "server": addr,
        "port": int(port) if port.isdigit() else 0,
        "auth": auth,
        "sni": str(tls.get("sni", "") or ""),
        "skip_cert_verify": bool(tls.get("insecure", False)),
        "up": str(bw.get("up", "") or ""),
        "down": str(bw.get("down", "") or ""),
    }]


def parse_singbox(text: str) -> list[dict]:
    data = json.loads(text)
    if not isinstance(data, dict):
        return []
    nodes = []
    for ob in data.get("outbounds") or []:
        if not isinstance(ob, dict):
            continue
        if ob.get("type") == "hysteria":
            tls = ob.get("tls") or {}
            nodes.append({
                "protocol": "hysteria",
                "name": f"sg-{ob.get('tag', 'hyst')}",
                "server": str(ob.get("server", "") or ""),
                "port": int(ob.get("server_port", 0)),
                "auth": str(ob.get("auth_str", "") or ""),
                "sni": str(tls.get("server_name", "") or ""),
                "skip_cert_verify": bool(tls.get("insecure", False)),
                "alpn": tls.get("alpn") or [],
                "up": str(ob.get("up_mbps", "") or ""),
                "down": str(ob.get("down_mbps", "") or ""),
            })
    return nodes


def parse_xray(text: str) -> list[dict]:
    data = json.loads(text)
    if not isinstance(data, dict):
        return []
    nodes = []
    for ob in data.get("outbounds") or []:
        if not isinstance(ob, dict):
            continue
        proto = ob.get("protocol", "")
        if proto != "vless":
            continue
        settings = ob.get("settings") or {}
        stream = ob.get("streamSettings") or {}
        for v in settings.get("vnext") or []:
            for u in v.get("users") or []:
                network = stream.get("network", "tcp")
                security = stream.get("security", "")
                node = {
                    "protocol": "vless",
                    "name": f"xray-{ob.get('tag', 'proxy')}",
                    "server": str(v.get("address", "") or ""),
                    "port": int(v.get("port", 0)),
                    "uuid": str(u.get("id", "") or ""),
                    "encryption": str(u.get("encryption", "none") or "none"),
                    "network": network,
                    "security": security,
                }
                if security == "reality":
                    rs = stream.get("realitySettings") or {}
                    node.update(sni=str(rs.get("serverName", "") or ""),
                               fp=str(rs.get("fingerprint", "chrome") or "chrome"),
                               pbk=str(rs.get("publicKey", "") or ""),
                               sid=str(rs.get("shortId", "") or ""))
                if network == "xhttp":
                    xh = stream.get("xhttpSettings") or {}
                    node["path"] = str(xh.get("path", "") or "")
                elif network == "ws":
                    ws = stream.get("wsSettings") or {}
                    node["path"] = str(ws.get("path", "") or "")
                nodes.append(node)
    return nodes


def parse_juicity(text: str) -> list[dict]:
    data = json.loads(text)
    s = str(data.get("server", "") or "")
    if ":" in s:
        addr, port = s.rsplit(":", 1)
    else:
        addr, port = s, "0"
    return [{
        "protocol": "juicity",
        "name": "juicity-gitlab",
        "server": addr,
        "port": int(port) if port.isdigit() else 0,
        "uuid": str(data.get("uuid", "") or ""),
        "password": str(data.get("password", "dongtaiwang.com") or "dongtaiwang.com"),
        "sni": str(data.get("sni", "") or ""),
        "skip_cert_verify": bool(data.get("allow_insecure", False)),
    }]


PARSERS = {
    "clash.meta": parse_clash_meta,
    "hysteria": parse_hysteria,
    "hysteria2": parse_hysteria2,
    "singbox": parse_singbox,
    "xray": parse_xray,
    "juicity": parse_juicity,
}

# ---- URI Generators ----

def uri_vless(n: dict) -> str:
    p = [f"encryption={n.get('encryption', 'none')}"]
    if n.get("security") == "reality":
        p.append("security=reality")
        if n.get("sni"): p.append(f"sni={n['sni']}")
        if n.get("fp"): p.append(f"fp={n['fp']}")
        if n.get("pbk"): p.append(f"pbk={n['pbk']}")
        if n.get("sid"): p.append(f"sid={n['sid']}")
    net = n.get("network", "tcp")
    if net != "tcp": p.append(f"type={net}")
    if n.get("path"): p.append(f"path={n['path']}")
    return f"vless://{n['uuid']}@{n['server']}:{n['port']}?{'&'.join(p)}#{n['name']}"


def uri_hysteria(n: dict) -> str:
    p = ["protocol=udp"]
    if n.get("auth"): p.append(f"auth={n['auth']}")
    if n.get("sni"): p.append(f"peer={n['sni']}")
    if n.get("skip_cert_verify"): p.append("insecure=1")
    if n.get("alpn"): p.append(f"alpn={','.join(n['alpn'])}")
    up = str(n.get("up", "") or "").lower().replace("mbps", "").strip()
    down = str(n.get("down", "") or "").lower().replace("mbps", "").strip()
    if up and up.isdigit(): p.append(f"upmbps={up}")
    if down and down.isdigit(): p.append(f"downmbps={down}")
    return f"hysteria://{n['server']}:{n['port']}?{'&'.join(p)}#{n['name']}"


def uri_hysteria2(n: dict) -> str:
    p = []
    if n.get("sni"): p.append(f"sni={n['sni']}")
    if n.get("skip_cert_verify"): p.append("insecure=1")
    up = str(n.get("up", "") or "").lower().replace("mbps", "").strip()
    down = str(n.get("down", "") or "").lower().replace("mbps", "").strip()
    if up and up.isdigit(): p.append(f"upmbps={up}")
    if down and down.isdigit(): p.append(f"downmbps={down}")
    return f"hysteria2://{n['auth']}@{n['server']}:{n['port']}?{'&'.join(p)}#{n['name']}"


def uri_juicity(n: dict) -> str:
    p = []
    if n.get("sni"): p.append(f"sni={n['sni']}")
    if n.get("skip_cert_verify"): p.append("insecure=1")
    return f"juicity://{n['uuid']}:{n['password']}@{n['server']}:{n['port']}?{'&'.join(p)}#{n['name']}"


URI_GEN = {"vless": uri_vless, "hysteria": uri_hysteria, "hysteria2": uri_hysteria2, "juicity": uri_juicity}


# ---- Clash Proxy Builders ----

def clash_proxy(node: dict) -> dict | None:
    p = node["protocol"]
    if p == "hysteria":
        return {
            "name": node["name"], "type": "hysteria", "server": node["server"], "port": node["port"],
            "auth-str": node.get("auth", ""), "sni": node.get("sni", ""),
            "skip-cert-verify": node.get("skip_cert_verify", False),
            "alpn": node.get("alpn", ["h3"]), "protocol": "udp",
            "up": f"{safe_float(node.get('up'), 11):.0f} Mbps", "down": f"{safe_float(node.get('down'), 55):.0f} Mbps",
        }
    elif p == "hysteria2":
        return {
            "name": node["name"], "type": "hysteria2", "server": node["server"], "port": node["port"],
            "password": node.get("auth", ""), "sni": node.get("sni", ""),
            "skip-cert-verify": node.get("skip_cert_verify", False),
            "up": f"{safe_float(node.get('up'), 11):.0f} Mbps", "down": f"{safe_float(node.get('down'), 55):.0f} Mbps",
        }
    elif p == "vless":
        c = {
            "name": node["name"], "type": "vless", "server": node["server"], "port": node["port"],
            "uuid": node.get("uuid", ""), "network": node.get("network", "tcp"),
            "tls": node.get("security") in ("tls", "reality"),
            "servername": node.get("sni", ""),
        }
        if node.get("security") == "reality":
            c["reality-opts"] = {"public-key": node.get("pbk", ""), "short-id": node.get("sid", "")}
            c["client-fingerprint"] = node.get("fp", "chrome")
        return c
    return None


# ---- WARP ----

def load_warp() -> dict | None:
    cf = OUTPUT_DIR / "warp_config.json"
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8"))
    return None


def warp_clash(w: dict) -> dict:
    la = w.get("local_address")
    if isinstance(la, list) and la:
        ip = str(la[0])
    elif isinstance(la, str) and la:
        ip = la
    else:
        ip = "172.16.0.2/32"
    ep = str(w.get("peer_endpoint", "engage.cloudflareclient.com:2408"))
    return {
        "name": "WARP", "type": "wireguard",
        "server": ep.split(":")[0] if ":" in ep else ep,
        "port": 2408, "ip": ip,
        "private-key": str(w.get("private_key", "")),
        "public-key": str(w.get("peer_public_key", "")),
        "mtu": 1280,
    }


def warp_singbox(w: dict) -> dict:
    la = w.get("local_address")
    if not isinstance(la, list) or not la:
        la = ["172.16.0.2/32"]
    return {
        "type": "wireguard", "tag": "warp-out",
        "local_address": la,
        "private_key": str(w.get("private_key", "")),
        "mtu": 1280,
        "peers": [{
            "address": str(w.get("peer_endpoint", "engage.cloudflareclient.com:2408")),
            "port": 2408,
            "public_key": str(w.get("peer_public_key", "")),
            "pre_shared_key": "",
            "allowed_ips": ["0.0.0.0/0", "::/0"],
        }],
    }


# ---- Main ----

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_nodes = []

    print("=" * 60)
    print("Step 1: Fetching proxy configs...")
    print("=" * 60)

    for name, urls in GITLAB_SOURCES.items():
        print(f"\n[{name}]")
        text = fetch(name, urls)
        if text is None:
            continue
        parser = PARSERS.get(name)
        if parser is None:
            continue
        parsed = parser(text)
        print(f"  Parsed {len(parsed)} node(s)")
        all_nodes.extend(parsed)

    print(f"\nTotal: {len(all_nodes)} nodes")

    if not all_nodes:
        print("[ERROR] No nodes found.")
        sys.exit(1)

    # Share URIs
    print("\n" + "=" * 60)
    print("Step 2: Generating share URIs...")
    print("=" * 60)
    uris = []
    for n in all_nodes:
        g = URI_GEN.get(n["protocol"])
        if g:
            uris.append(g(n))

    # Clash config
    print("\n" + "=" * 60)
    print("Step 3: Generating Clash config...")
    print("=" * 60)
    clash_proxies = []
    for n in all_nodes:
        cp = clash_proxy(n)
        if cp:
            clash_proxies.append(cp)

    # WARP
    print("\n" + "=" * 60)
    print("Step 4: WARP integration...")
    print("=" * 60)
    warp = load_warp()
    if warp:
        print("[WARP] Cached config found")
        clash_proxies.append(warp_clash(warp))
        print("[OK] WARP added to Clash proxies")
    else:
        print("[WARP] No cached config")

    # Sing-box config with WARP chain
    if warp:
        print("\n" + "=" * 60)
        print("Step 5: Generating sing-box config (proxy -> WARP chain)...")
        print("=" * 60)

        sg_outbounds = []
        for n in all_nodes:
            p = n["protocol"]
            tag = n["name"][:40]
            if p in ("hysteria", "hysteria2"):
                sg_outbounds.append({
                    "type": p, "tag": tag,
                    "server": n["server"], "server_port": n["port"],
                    ("auth_str" if p == "hysteria" else "password"): n.get("auth", ""),
                    "tls": {"enabled": True, "insecure": n.get("skip_cert_verify", False),
                            "server_name": n.get("sni", ""),
                            "alpn": n.get("alpn", ["h3"])},
                })
                if p == "hysteria":
                    sg_outbounds[-1]["up_mbps"] = int(safe_float(n.get("up"), 11))
                    sg_outbounds[-1]["down_mbps"] = int(safe_float(n.get("down"), 55))
            elif p == "vless":
                ob = {
                    "type": "vless", "tag": tag,
                    "server": n["server"], "server_port": n["port"],
                    "uuid": n.get("uuid", ""), "flow": "",
                    "transport": {"type": n.get("network", "tcp")},
                }
                if n.get("security") == "reality":
                    ob["tls"] = {"enabled": True, "server_name": n.get("sni", ""),
                                  "reality": {"enabled": True, "public_key": n.get("pbk", ""),
                                              "short_id": n.get("sid", "")},
                                  "utls": {"enabled": True, "fingerprint": "chrome"}}
                else:
                    ob["tls"] = {"enabled": False}
                if n.get("path"):
                    ob["transport"]["path"] = n["path"]
                sg_outbounds.append(ob)

        # WARP outbound
        sg_outbounds.append(warp_singbox(warp))
        # Detour outbound: proxy -> WARP
        proxy_tags = [ob["tag"] for ob in sg_outbounds if ob["type"] not in ("wireguard", "selector")]
        sg_outbounds.append({
            "type": "selector", "tag": "proxy", "outbounds": proxy_tags,
        })

        sg_config = {
            "log": {"level": "info"},
            "inbounds": [{"type": "mixed", "tag": "mixed-in", "listen": "127.0.0.1", "listen_port": 1080}],
            "outbounds": sg_outbounds,
            "route": {
                "rules": [
                    {"outbound": "warp-out", "network": "udp"},
                    {"outbound": "warp-out", "domain_suffix": ["google.com", "youtube.com", "twitter.com", "github.com", "openai.com", "cloudflare.com"]},
                    {"outbound": "proxy", "geosite": "geolocation-!cn"},
                    {"outbound": "direct", "geosite": "cn"},
                    {"outbound": "direct", "geoip": "cn"},
                ],
                "final": "warp-out",
            },
        }
        (OUTPUT_DIR / "singbox_config.json").write_text(
            json.dumps(sg_config, indent=2, ensure_ascii=False), encoding="utf-8")
        print("[OK] singbox_config.json (proxy -> WARP chain)")

    # Write outputs
    print("\n" + "=" * 60)
    print("Step 6: Writing remaining outputs...")
    print("=" * 60)

    (OUTPUT_DIR / "share_links.txt").write_text("\n".join(uris), encoding="utf-8")
    sub_b64 = base64.b64encode("\n".join(uris).encode()).decode()
    (OUTPUT_DIR / "subscription_b64.txt").write_text(sub_b64, encoding="utf-8")

    clash_yaml = yaml.dump({
        "mixed-port": 7890, "allow-lan": False, "log-level": "info",
        "proxies": clash_proxies,
    }, allow_unicode=True, default_flow_style=False, sort_keys=False, width=200)
    (OUTPUT_DIR / "clash_config.yaml").write_text(clash_yaml, encoding="utf-8")

    (OUTPUT_DIR / "all_nodes.json").write_text(
        json.dumps(all_nodes, indent=2, ensure_ascii=False), encoding="utf-8")

    # Stats
    stats = {}
    for n in all_nodes:
        stats[n["protocol"]] = stats.get(n["protocol"], 0) + 1

    print()
    print(f"{'='*60}")
    print("BUILD COMPLETE")
    print(f"{'='*60}")
    print(f"Nodes: {len(all_nodes)} | URIs: {len(uris)} | Clash proxies: {len(clash_proxies)}")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    if warp:
        print("WARP: integrated")


if __name__ == "__main__":
    main()
