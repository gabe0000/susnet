# Susnet Quickstart

## 1) Connect over Tailscale
```bash
ssh gabe0000@100.90.138.26
```

## 2) Verify core services
```bash
sudo docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "openclaw|ollama|mosquitto|nodered|susnet-core-api"
sudo systemctl status joe-cabot-lite --no-pager
```

## 3) Sync Joe runtime from tracked repo source
```bash
cd ~/sync-work/susnet-sync
./scripts/deploy-joe-cabot-lite.sh
cat /home/codex/joe-cabot-lite/DEPLOYED_FROM_REPO
```

## 4) Directly query Joe Cabot from SSH terminal
Terminal A:
```bash
sudo docker exec -it susnet-next-mosquitto sh -lc "mosquitto_sub -h 100.124.168.35 -p 1883 -t 'susnet/agent/#' -v"
```

Terminal B:
```bash
RID="$(date +%s)-$RANDOM"
TS="$(date +%s)"
EXP="$((TS+120))"
sudo docker exec -i susnet-next-mosquitto sh -lc "mosquitto_pub -h 100.124.168.35 -p 1883 -t susnet/agent/query -m '{\"request_id\":\"'$RID'\",\"session_id\":\"sess-'$RID'\",\"text\":\"what is 2+2\",\"sender\":{\"node_id\":\"!9e77f1a0\",\"shortname\":\"GETB\",\"longname\":\"GETB\"},\"channel_index\":1,\"origin\":\"meshtastic\",\"created_ts\":'$TS',\"expires_ts\":'$EXP',\"trace\":{\"edge_host\":\"meshbox\",\"control_host\":\"susnet\",\"version\":\"quickstart\"}}'"
```

## 5) Simplest direct CLI
```bash
joe "what is 2+2"
joe "traffic load summary please"
joe --chat
```

## 6) OpenClaw endpoint over Tailscale
- primary endpoint: `susnet:18789`

## 7) Check storage layout
```bash
findmnt -no SOURCE,SIZE,AVAIL,USE% /
findmnt -no SOURCE,SIZE,AVAIL,USE% /data
df -h / /data
```
