#!/usr/bin/env python3
"""
Nodes Converter — 每日从 GitLab 源拉取代理节点配置，转换为 v2rayN / Clash 格式，并可选套 WARP 出站。
"""
import json
import yaml
import os
import re
import sys
import requests
from pathlib import Path

# ============================================================
# Configuration — modify these for your own fork
# ============================================================
GITLAB_SOURCES = {
    # clash.meta config
    "clash.meta": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/clash.meta2/1/config.yaml",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/clash.meta2/1/config.yaml",
    ],
    # hysteria config
    "hysteria": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/hysteria/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/hysteria/1/config.json",
    ],
    # hysteria2 config
    "hysteria2": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/hysteria2/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/hysteria2/1/config.json",
    ],
    # singbox config
    "singbox": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/singbox/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/singbox/1/config.json",
    ],
    # Xray config
    "xray": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/xray/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/xray/1/config.json",
    ],
    # juicity config
    "juicity": [
        "https://www.gitlabip.xyz/Alvin9999/PAC/refs/heads/master/backup/img/1/2/ipp/juicity/1/config.json",
        "https://gitlab.com/free9999/ipupdate/-/raw/master/backup/img/1/2/ipp/juicity/1/config.json",
    ],
}

OUTPUT_DIR = Path("output")


def fetch_config(urls: list[str]) -> str | None:
    """Try fetching from multiple mirror URLs."""
    for url in urls:
        try:
            resp = requests.get(url, timeout=30, verify=False)
            resp.raise_for_status()
            print(f"  [OK] {url[:60]}...")
            return resp.text
        except Exception as e:
            print(f"  [FAIL] {url[:60]}...: {e}")
    return None


def parse_clash_meta_yaml(text: str, source_name: str) -> list[dict]:
    """Parse clash.meta config.yaml -> extract individual proxies."""
    try:
        data = yaml.safe_load(text)
    except Exception as e:
        print(f"  [ERROR] YAML parse failed for {source_name}: {e}")
        return []

    nodes = []
    proxies = data.get('proxies', []) if isinstance(data, dict) else []

    for p in proxies:
        if not isinstance(p, dict):
            continue
        ptype = p.get('type', '')

        node = {
            "source": source_name,
            "name": p.get('name', f'{source_name}-node'),
            "protocol": ptype,
            "server": p.get('server', ''),
            "port": p.get('port', 0),
            "auth": p.get('auth-str', p.get('password', '')),
            "sni": p.get('sni', ''),
            "skip_cert_verify": p.get('skip-cert-verify', False),
            "alpn": p.get('alpn', []),
            "up": str(p.get('up', '')),
            "down": str(p.get('down', '')),
        }
        nodes.append(node)

    return nodes


def parse_hysteria_json(text: str, source_name: str) -> list[dict]:
    """Parse hysteria v1 config.json."""
    try:
        data = json.loads(text)
    except:
        return []

    server = data.get('server', '')
    if ':' in server:
        addr, port = server.rsplit(':', 1)
    else:
        addr, port = server, '0'

    return [{
        "source": source_name,
        "name": f"hysteria-{source_name}",
        "protocol": "hysteria",
        "server": addr,
        "port": int(port) if port.isdigit() else 0,
        "auth": data.get('auth_str', ''),
        "sni": data.get('server_name', ''),
        "skip_cert_verify": data.get('insecure', False),
        "alpn": [data.get('alpn', 'h3')],
        "up": str(data.get('up_mbps', '')),
        "down": str(data.get('down_mbps', '')),
    }]


def parse_hysteria2_json(text: str, source_name: str) -> list[dict]:
    """Parse hysteria v2 config.json."""
    try:
        data = json.loads(text)
    except:
        return []

    server_str = data.get('server', '')
    auth = data.get('auth', '')
    tls = data.get('tls', {}) or {}
    sni = tls.get('sni', '')
    insecure = tls.get('insecure', False)
    bw = data.get('bandwidth', {}) or {}
    up = str(bw.get('up', ''))
    down = str(bw.get('down', ''))

    # Parse server:port
    main_part = server_str.split(',')[0].strip()
    if main_part.startswith('['):
        m = re.match(r'^\[(.+?)\]:(\d+)$', main_part)
        if m:
            addr, port = m.group(1), m.group(2)
        else:
            addr, port = main_part, '0'
    elif ':' in main_part:
        addr, port = main_part.rsplit(':', 1)
    else:
        addr, port = main_part, '0'

    return [{
        "source": source_name,
        "name": f"hysteria2-{source_name}",
        "protocol": "hysteria2",
        "server": addr,
        "port": int(port) if port.isdigit() else 0,
        "auth": auth,
        "sni": sni,
        "skip_cert_verify": insecure,
        "up": up,
        "down": down,
    }]


def parse_singbox_json(text: str, source_name: str) -> list[dict]:
    """Parse sing-box config.json -> extract outbounds."""
    try:
        data = json.loads(text)
    except:
        return []

    nodes = []
    for ob in data.get('outbounds', []) if isinstance(data, dict) else []:
        if not isinstance(ob, dict):
            continue
        if ob.get('type') == 'hysteria':
            tls = ob.get('tls', {}) or {}
            nodes.append({
                "source": source_name,
                "name": f"singbox-hysteria-{ob.get('tag', source_name)}",
                "protocol": "hysteria",
                "server": ob.get('server', ''),
                "port": ob.get('server_port', 0),
                "auth": ob.get('auth_str', ''),
                "sni": tls.get('server_name', ''),
                "skip_cert_verify": tls.get('insecure', False),
                "alpn": tls.get('alpn', []),
                "up": str(ob.get('up_mbps', '')),
                "down": str(ob.get('down_mbps', '')),
            })
    return nodes


def parse_xray_json(text: str, source_name: str) -> list[dict]:
    """Parse Xray config.json -> extract outbounds."""
    try:
        data = json.loads(text)
    except:
        return []

    nodes = []
    for ob in data.get('outbounds', []) if isinstance(data, dict) else []:
        if not isinstance(ob, dict):
            continue
        protocol = ob.get('protocol', '')
        settings = ob.get('settings', {}) or {}
        stream = ob.get('streamSettings', {}) or {}

        if protocol == 'vless':
            for v in settings.get('vnext', []):
                addr = v.get('address', '')
                pport = v.get('port', 0)
                for u in v.get('users', []):
                    network = stream.get('network', 'tcp')
                    security = stream.get('security', '')

                    node = {
                        "source": source_name,
                        "name": f"xray-vless-{ob.get('tag', source_name)}",
                        "protocol": "vless",
                        "server": addr,
                        "port": pport,
                        "uuid": u.get('id', ''),
                        "encryption": u.get('encryption', 'none'),
                        "flow": u.get('flow', ''),
                        "network": network,
                        "security": security,
                    }

                    if security == 'reality':
                        rs = stream.get('realitySettings', {}) or {}
                        node.update({
                            "sni": rs.get('serverName', ''),
                            "fp": rs.get('fingerprint', 'chrome'),
                            "pbk": rs.get('publicKey', ''),
                            "sid": rs.get('shortId', ''),
                            "spx": rs.get('spiderX', ''),
                        })

                    if network == 'xhttp':
                        xh = stream.get('xhttpSettings', {}) or {}
                        node["path"] = xh.get('path', '')
                    elif network == 'ws':
                        ws = stream.get('wsSettings', {}) or {}
                        node["path"] = ws.get('path', '')

                    nodes.append(node)

    return nodes


def parse_juicity_json(text: str, source_name: str) -> list[dict]:
    """Parse juicity config.json."""
    try:
        data = json.loads(text)
    except:
        return []

    server_str = data.get('server', '')
    if ':' in server_str:
        addr, port = server_str.rsplit(':', 1)
    else:
        addr, port = server_str, '0'

    return [{
        "source": source_name,
        "name": f"juicity-{source_name}",
        "protocol": "juicity",
        "server": addr,
        "port": int(port) if port.isdigit() else 0,
        "uuid": data.get('uuid', ''),
        "password": data.get('password', 'dongtaiwang.com'),
        "sni": data.get('sni', ''),
        "skip_cert_verify": data.get('allow_insecure', False),
    }]


PARSERS = {
    "clash.meta": parse_clash_meta_yaml,
    "hysteria": parse_hysteria_json,
    "hysteria2": parse_hysteria2_json,
    "singbox": parse_singbox_json,
    "xray": parse_xray_json,
    "juicity": parse_juicity_json,
}


# ============================================================
# URI Generators
# ============================================================

def gen_vless_uri(node: dict) -> str:
    params = [f"encryption={node.get('encryption', 'none')}"]
    if node.get('security') == 'reality':
        params.append("security=reality")
        if node.get('sni'): params.append(f"sni={node['sni']}")
        if node.get('fp'): params.append(f"fp={node['fp']}")
        if node.get('pbk'): params.append(f"pbk={node['pbk']}")
        if node.get('sid'): params.append(f"sid={node['sid']}")
        if node.get('spx'): params.append(f"spx={node['spx']}")
    network = node.get('network', 'tcp')
    if network != 'tcp': params.append(f"type={network}")
    if node.get('path'): params.append(f"path={node['path']}")
    if node.get('flow'): params.append(f"flow={node['flow']}")
    name = node['name'].replace(' ', '%20')
    return f"vless://{node['uuid']}@{node['server']}:{node['port']}?{'&'.join(params)}#{name}"


def gen_hysteria_uri(node: dict) -> str:
    params = ["protocol=udp"]
    if node.get('auth'): params.append(f"auth={node['auth']}")
    if node.get('sni'): params.append(f"peer={node['sni']}")
    if node.get('skip_cert_verify'): params.append("insecure=1")
    if node.get('alpn'): params.append(f"alpn={','.join(node['alpn'])}")
    up = str(node.get('up', '')).replace(' Mbps', '').strip()
    down = str(node.get('down', '')).replace(' Mbps', '').strip()
    if up and up != '': params.append(f"upmbps={up}")
    if down and down != '': params.append(f"downmbps={down}")
    name = node['name'].replace(' ', '%20')
    return f"hysteria://{node['server']}:{node['port']}?{'&'.join(params)}#{name}"


def gen_hysteria2_uri(node: dict) -> str:
    params = []
    if node.get('sni'): params.append(f"sni={node['sni']}")
    if node.get('skip_cert_verify'): params.append("insecure=1")
    up = str(node.get('up', '')).replace(' mbps', '').strip()
    down = str(node.get('down', '')).replace(' mbps', '').strip()
    if up and up != '': params.append(f"upmbps={up}")
    if down and down != '': params.append(f"downmbps={down}")
    name = node['name'].replace(' ', '%20')
    return f"hysteria2://{node['auth']}@{node['server']}:{node['port']}?{'&'.join(params)}#{name}"


def gen_juicity_uri(node: dict) -> str:
    params = []
    if node.get('sni'): params.append(f"sni={node['sni']}")
    if node.get('skip_cert_verify'): params.append("insecure=1")
    name = node['name'].replace(' ', '%20')
    return f"juicity://{node['uuid']}:{node['password']}@{node['server']}:{node['port']}?{'&'.join(params)}#{name}"


URI_GENERATORS = {
    "vless": gen_vless_uri,
    "hysteria": gen_hysteria_uri,
    "hysteria2": gen_hysteria2_uri,
    "juicity": gen_juicity_uri,
}

CLASH_TYPE_MAP = {
    "hysteria": "hysteria",
    "hysteria2": "hysteria2",
    "vless": "vless",
    "juicity": "juicity",
}


# ============================================================
# WARP Integration
# ============================================================

def load_warp_config() -> dict | None:
    """Load cached WARP WireGuard config."""
    cache_file = OUTPUT_DIR / "warp_config.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None


def build_warp_singbox_outbound(warp: dict) -> dict:
    """Build sing-box WireGuard outbound for WARP."""
    return {
        "type": "wireguard",
        "tag": "warp-out",
        "local_address": warp.get("local_address", ["172.16.0.2/32"]),
        "private_key": warp.get("private_key", ""),
        "mtu": 1280,
        "peers": [{
            "address": warp.get("peer_endpoint", "engage.cloudflareclient.com:2408"),
            "port": 2408,
            "public_key": warp.get("peer_public_key", ""),
            "pre_shared_key": "",
            "allowed_ips": ["0.0.0.0/0", "::/0"],
            "reserved": "",
        }],
    }


def build_warp_clash_proxy(warp: dict) -> dict:
    """Build clash.meta WireGuard proxy for WARP."""
    return {
        "name": "WARP",
        "type": "wireguard",
        "server": warp.get("peer_endpoint", "engage.cloudflareclient.com:2408").split(":")[0],
        "port": 2408,
        "ip": warp.get("local_address", ["172.16.0.2/32"])[0] if warp.get("local_address") else "172.16.0.2/32",
        "private-key": warp.get("private_key", ""),
        "public-key": warp.get("peer_public_key", ""),
        "mtu": 1280,
    }


# ============================================================
# Main
# ============================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Disable SSL warnings for mirrors
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    all_nodes = []

    # 1. Fetch and parse all sources
    print("=" * 60)
    print("Step 1: Fetching proxy configs from GitLab mirrors...")
    print("=" * 60)

    for source_name, urls in GITLAB_SOURCES.items():
        print(f"\n[{source_name}]")
        text = fetch_config(urls)
        if text is None:
            print(f"  [SKIP] All mirrors failed for {source_name}")
            continue

        parser = PARSERS.get(source_name)
        if parser is None:
            print(f"  [SKIP] No parser for {source_name}")
            continue

        nodes = parser(text, source_name)
        print(f"  Parsed {len(nodes)} node(s)")
        all_nodes.extend(nodes)

    print(f"\nTotal nodes parsed: {len(all_nodes)}")

    if not all_nodes:
        print("[ERROR] No nodes found. Check network or GitLab availability.")
        sys.exit(1)

    # 2. Generate share links
    print("\n" + "=" * 60)
    print("Step 2: Generating share URIs...")
    print("=" * 60)

    uris = []
    for node in all_nodes:
        gen = URI_GENERATORS.get(node["protocol"])
        if gen:
            uri = gen(node)
            uris.append(uri)
            print(f"  [{node['protocol']}] {node['name']}")

    # 3. Generate Clash config
    print("\n" + "=" * 60)
    print("Step 3: Generating Clash config...")
    print("=" * 60)

    clash_proxies = []
    for node in all_nodes:
        proto = node["protocol"]
        clash_type = CLASH_TYPE_MAP.get(proto)
        if clash_type == "hysteria":
            clash_proxies.append({
                "name": node["name"],
                "type": "hysteria",
                "server": node["server"],
                "port": node["port"],
                "auth-str": node.get("auth", ""),
                "sni": node.get("sni", ""),
                "skip-cert-verify": node.get("skip_cert_verify", False),
                "alpn": node.get("alpn", ["h3"]),
                "protocol": "udp",
                "up": f"{node.get('up', '11')} Mbps",
                "down": f"{node.get('down', '55')} Mbps",
            })
        elif clash_type == "hysteria2":
            clash_proxies.append({
                "name": node["name"],
                "type": "hysteria2",
                "server": node["server"],
                "port": node["port"],
                "password": node.get("auth", ""),
                "sni": node.get("sni", ""),
                "skip-cert-verify": node.get("skip_cert_verify", False),
                "up": f"{node.get('up', '11')} Mbps",
                "down": f"{node.get('down', '55')} Mbps",
            })
        elif clash_type == "vless":
            clash_proxies.append({
                "name": node["name"],
                "type": "vless",
                "server": node["server"],
                "port": node["port"],
                "uuid": node.get("uuid", ""),
                "network": node.get("network", "tcp"),
                "tls": node.get("security") in ("tls", "reality"),
                "servername": node.get("sni", ""),
                "reality-opts": {
                    "public-key": node.get("pbk", ""),
                    "short-id": node.get("sid", ""),
                } if node.get("security") == "reality" else {},
                "client-fingerprint": node.get("fp", "chrome"),
            })

    # 4. Try WARP integration
    print("\n" + "=" * 60)
    print("Step 4: WARP integration...")
    print("=" * 60)

    warp_config = load_warp_config()
    if warp_config:
        print("[WARP] Cached config found, adding to outputs")
        # Add WARP WireGuard proxy to clash config
        clash_proxies.append(build_warp_clash_proxy(warp_config))

        # Generate sing-box config with WARP
        warp_outbound = build_warp_singbox_outbound(warp_config)

        # Build sing-box with chain: inbound → selector → proxy → WARP
        sg_outbounds = []
        for node in all_nodes:
            proto = node["protocol"]
            if proto == "hysteria":
                sg_outbounds.append({
                    "type": "hysteria",
                    "tag": node["name"][:40],
                    "server": node["server"],
                    "server_port": node["port"],
                    "auth_str": node.get("auth", ""),
                    "up_mbps": int(float(node.get("up", "11").replace("Mbps","").strip() or 11)),
                    "down_mbps": int(float(node.get("down", "55").replace("Mbps","").strip() or 55)),
                    "tls": {
                        "enabled": True,
                        "insecure": node.get("skip_cert_verify", False),
                        "server_name": node.get("sni", ""),
                        "alpn": node.get("alpn", ["h3"]),
                    },
                })
            elif proto == "hysteria2":
                sg_outbounds.append({
                    "type": "hysteria2",
                    "tag": node["name"][:40],
                    "server": node["server"],
                    "server_port": node["port"],
                    "password": node.get("auth", ""),
                    "up_mbps": int(float(node.get("up", "55").replace("Mbps","").strip() or 55)),
                    "down_mbps": int(float(node.get("down", "11").replace("Mbps","").strip() or 11)),
                    "tls": {
                        "enabled": True,
                        "insecure": node.get("skip_cert_verify", False),
                        "server_name": node.get("sni", ""),
                    },
                })
            elif proto == "vless":
                sg_outbounds.append({
                    "type": "vless",
                    "tag": node["name"][:40],
                    "server": node["server"],
                    "server_port": node["port"],
                    "uuid": node.get("uuid", ""),
                    "flow": "",
                    "tls": {
                        "enabled": node.get("security") == "reality",
                        "server_name": node.get("sni", ""),
                        "reality": {
                            "enabled": node.get("security") == "reality",
                            "public_key": node.get("pbk", ""),
                            "short_id": node.get("sid", ""),
                        },
                        "utls": {"enabled": True, "fingerprint": "chrome"},
                    } if node.get("security") == "reality" else {"enabled": False},
                    "transport": {
                        "type": node.get("network", "tcp"),
                        "path": node.get("path", ""),
                    },
                })

        # Add WARP outbound
        sg_outbounds.append(warp_outbound)

        # Add selector + urltest that chains through node → WARP
        sg_outbounds.append({
            "type": "selector",
            "tag": "proxy",
            "outbounds": [ob["tag"] for ob in sg_outbounds if ob["tag"] != "warp-out" and ob["type"] != "selector"],
        })

        sg_config = {
            "log": {"level": "info"},
            "inbounds": [{
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 1080,
            }],
            "outbounds": sg_outbounds,
            "route": {
                "rules": [
                    {"outbound": "proxy", "domain_suffix": ["google.com", "youtube.com", "twitter.com", "github.com"]},
                    {"outbound": "proxy", "geosite": "geolocation-!cn"},
                    {"outbound": "warp-out", "network": "udp"},
                    {"outbound": "direct", "geosite": "cn"},
                    {"outbound": "direct", "geoip": "cn"},
                ],
                "final": "proxy",
            },
        }

        with open(OUTPUT_DIR / "singbox_config.json", 'w', encoding='utf-8') as f:
            json.dump(sg_config, f, indent=2, ensure_ascii=False)
        print("[OK] singbox_config.json (with WARP)")
    else:
        print("[WARP] No cached config — run scripts/warp.py first, or action will auto-register")
        print("[WARP] If running in GitHub Actions, WARP registration is automatic.")

    # 5. Write output files
    print("\n" + "=" * 60)
    print("Step 5: Writing outputs...")
    print("=" * 60)

    # share_links.txt
    links_text = "\n".join(uris)
    with open(OUTPUT_DIR / "share_links.txt", 'w', encoding='utf-8') as f:
        f.write(links_text)

    # base64 encode for subscription
    links_b64 = base64.b64encode(links_text.encode('utf-8')).decode('utf-8')
    with open(OUTPUT_DIR / "subscription_b64.txt", 'w', encoding='utf-8') as f:
        f.write(links_b64)

    # clash_config.yaml
    clash_yaml = yaml.dump({
        "mixed-port": 7890,
        "allow-lan": False,
        "log-level": "info",
        "proxies": clash_proxies,
    }, allow_unicode=True, default_flow_style=False, sort_keys=False, width=200)

    with open(OUTPUT_DIR / "clash_config.yaml", 'w', encoding='utf-8') as f:
        f.write(clash_yaml)

    # all_nodes.json
    with open(OUTPUT_DIR / "all_nodes.json", 'w', encoding='utf-8') as f:
        json.dump(all_nodes, f, indent=2, ensure_ascii=False)

    # Stats
    stats = {}
    for node in all_nodes:
        proto = node.get("protocol", "unknown")
        stats[proto] = stats.get(proto, 0) + 1

    print(f"\n{'='*60}")
    print(f"BUILD COMPLETE")
    print(f"{'='*60}")
    print(f"Nodes: {len(all_nodes)}")
    for proto, count in sorted(stats.items()):
        print(f"  {proto}: {count}")
    print(f"Share URIs: {len(uris)}")
    print(f"Clash proxies: {len(clash_proxies)}")
    if warp_config:
        print(f"WARP: integrated")
    print(f"\nOutput: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
