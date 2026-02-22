# Susnet Quickstart

## 1) Connect
```bash
ssh codex@susnet
```

## 2) Verify core services
```bash
sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -E 'openclaw|ollama|mosquitto|nodered|susnet-core-api'
sudo systemctl status joe-cabot-lite --no-pager
```

## 3) Directly query Joe Cabot from SSH terminal
Terminal A:
```bash
sudo docker exec -it susnet-next-mosquitto sh -lc 'mosquitto_sub -h meshbox -p 1883 -t susnet/agent/reply'
```

Terminal B:
```bash
RID=$(date +%s)-$RANDOM
sudo docker exec -i susnet-next-mosquitto sh -lc "mosquitto_pub -h meshbox -p 1883 -t susnet/agent/query -m '{\"request_id\":\"$RID\",\"sender\":\"!9e77f1a0\",\"text\":\"traffic load summary please\"}'"
```

## 4) Check storage layout
```bash
findmnt -no SOURCE,SIZE,AVAIL,USE% /
findmnt -no SOURCE,SIZE,AVAIL,USE% /data
df -h / /data
```

## 5) OpenClaw endpoint over Tailscale
- Primary endpoint: `susnet:18789`
- Internally proxied to host-local `localhost:28789` via `tailscale serve`.
