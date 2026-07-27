#!/usr/bin/env python3
"""
Cloudflare WARP account registration — generates WireGuard credentials.
Run once to get WARP config, or it auto-runs in GitHub Actions.
"""
import json
import base64
import requests
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives import serialization

WARP_API = "https://api.cloudflareclient.com/v0a2158/reg"
OUTPUT = Path("output")
CACHE_FILE = OUTPUT / "warp_config.json"


def generate_keypair():
    private_key = X25519PrivateKey.generate()
    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    return base64.b64encode(private_bytes).decode(), base64.b64encode(public_bytes).decode()


def register_warp(public_key: str) -> dict:
    headers = {
        "CF-Client-Version": "a-7.21-0721",
        "Content-Type": "application/json",
    }
    body = {
        "key": public_key,
        "install_id": "",
        "fcm_token": "",
        "tos": "2024-09-23T00:00:00.000Z",
        "model": "PC",
        "serial_number": "github-actions",
        "locale": "en_US",
    }

    endpoints = [
        "https://api.cloudflareclient.com/v0a2158/reg",
        "https://api.cloudflareclient.com/v0a2483/reg",
    ]

    for ep in endpoints:
        try:
            resp = requests.post(ep, json=body, headers=headers, timeout=30)
            if resp.status_code == 200:
                print(f"[OK] WARP registration via {ep}")
                return resp.json()
        except Exception as e:
            print(f"[WARN] {ep}: {e}")

    raise RuntimeError("All WARP API endpoints failed")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)

    if CACHE_FILE.exists():
        print("[SKIP] WARP config already cached.")
        with open(CACHE_FILE) as f:
            wg = json.load(f)
        print(f"  Account: {wg.get('account_id', 'unknown')[:12]}...")
        return

    print("[WARP] Generating keypair...")
    private_key, public_key = generate_keypair()

    print("[WARP] Registering with Cloudflare...")
    data = register_warp(public_key)
    account = data.get("account", {})
    print(f"[WARP] Account ID: {account.get('id', 'unknown')[:20]}...")
    print(f"[WARP] Account Type: {account.get('account_type', 'free')}")
    print(f"[WARP] Licensed: {account.get('license', 'no')}")

    config = data.get("config", {})
    interface = config.get("interface", {})
    peer = config.get("peers", [{}])[0] if config.get("peers") else {}
    endpoint = peer.get("endpoint", {})

    wg_config = {
        "private_key": private_key,
        "local_address": interface.get("addresses", ["172.16.0.2/32"]),
        "peer_public_key": peer.get("public_key", ""),
        "peer_endpoint": endpoint.get("host", "engage.cloudflareclient.com:2408"),
        "client_id": config.get("client_id", ""),
        "account_id": account.get("id", ""),
        "account_type": account.get("account_type", "free"),
    }

    with open(CACHE_FILE, 'w') as f:
        json.dump(wg_config, f, indent=2)
    print(f"[OK] WARP config saved to {CACHE_FILE}")


if __name__ == "__main__":
    main()
