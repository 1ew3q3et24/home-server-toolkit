# home-server-toolkit

Tiny, dependency-light scripts for running services on a **dynamic home IP**:

- keep a DNS record in sync with your public IPv4 (provider API)
- detect the public IP changing and notify a control plane over HTTPS + HMAC
- send a heartbeat only while the game server is actually listening
- fail over a Minecraft server between home and cloud without two writers on one world
- snapshot/rotate world backups with a systemd user timer

> 中文说明在后半部分。Everything here is generic: **no keys, no domains, no IPs** — fill in your own via `600` env files.

## Components

| Path | What it does |
|---|---|
| `ddns/ddns.sh` | Reads the current public IPv4 from several sources, compares it against the record served by the DNS provider API, PATCHes only on change. Retries with backoff. |
| `ddns/set-key.sh` | Writes the API key into a `600` env file with a non-echoing prompt. |
| `heartbeat/ipcheck.sh` | Every minute: detect public IP, POST `/ipchange` (HMAC-signed) when it changes. |
| `heartbeat/send.sh` | Heartbeat `/hb`, sent **only** if the local port is actually listening. Also warns when the LAN IP drifts away from the router port-forward target. |
| `heartbeat/hbsign.py` | `HMAC-SHA256(secret, message)` helper; the secret is read from a file, never from argv. |
| `minecraft-backup/backup.sh` | `save-all flush` → tar the world/plugins/config → keep N copies. |

## Design rules

1. **Secrets never touch argv, logs or the repo.** Keys live in `~/.config/<app>/*.env` with mode `600`; scripts `source` them.
2. **Fail closed.** No public IP, no majority agreement between sources, or no key → the script logs and exits without writing DNS.
3. **One writer per record.** The home box and the cloud never both update the same DNS record.
4. **Read the API truth, not DNS cache.** The updater asks the provider what the record currently says instead of resolving the name.

## Install

```bash
git clone https://github.com/<you>/home-server-toolkit.git
install -m 700 -d ~/ddns ~/heartbeat
install -m 700 ddns/ddns.sh ddns/set-key.sh ~/ddns/
install -m 700 heartbeat/*.sh heartbeat/hbsign.py ~/heartbeat/
install -m 644 heartbeat/*.service heartbeat/*.timer ~/.config/systemd/user/
~/.config/systemd/user# systemctl --user daemon-reload
~/.config/systemd/user# systemctl --user enable --now ipcheck.timer heartbeat.timer
```

### Environment (names only)

| Variable | Where | Meaning |
|---|---|---|
| `RAINYUN_API_KEY` | `~/.config/ddns/ddns.env` | provider API key |
| `DDNS_DOMAIN_ID`, `DDNS_HOST`, `DDNS_TTL`, `DDNS_LINE`, `DDNS_LEVEL` | same | which record to keep in sync |
| `CLOUD_URL` | `~/.config/heartbeat/hb.env` | control-plane base URL |
| token file | `~/.config/heartbeat/token` | HMAC secret, `600` |

## Known limitations

See [SECURITY-NOTES.md](SECURITY-NOTES.md). Short version: the heartbeat signature
covers `method|timestamp` but **not the request body**, and the replay window depends
entirely on the server-side clock check. PRs welcome.

## 中文说明

这套脚本解决的是「家里是动态公网 IP，但服务要一直可访问」这件事，分三层：

1. **DNS 层**（`ddns/`）：多来源取公网 IP 做交叉确认，再从 API 读当前记录，只有不一致才 PATCH，避免刷接口。
2. **通知层**（`heartbeat/`）：IP 一变就 HMAC 签名上报，云端据此决定要不要迁移服务；心跳只在服务真的在监听时才发，避免「进程活着但端口没开」的假活。
3. **数据层**（`minecraft-backup/`）：先让服务落盘再打包，按数量轮转，防止把「正在写入的存档」打成半个包。

原则：**密钥只存在于 600 文件**，不进代码、不进日志、不进命令行；任何一步拿不到可信输入就退出，绝不瞎写。

## License

MIT.
