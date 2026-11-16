# Host-level files (installed once per VPS, NOT by `docker compose up`)

`docker-autoheal.*` restarts containers whose healthcheck turned `unhealthy` (audit 2026-11-13
core-performance-04). Install on the VPS (one install covers every compose project on it):

```bash
sudo install -m 0755 config/host/docker-autoheal.sh /usr/local/bin/docker-autoheal.sh
sudo install -m 0644 config/host/docker-autoheal.service config/host/docker-autoheal.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now docker-autoheal.timer
systemctl list-timers docker-autoheal.timer && journalctl -t docker-autoheal --since today
```
