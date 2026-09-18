# SOC-Scale: Redis-Buffered SIEM Pipeline

A Docker Compose project that wires up a scalable SIEM log pipeline using **Redis** as a buffer between log collection (Wazuh/Filebeat) and analysis/indexing (Logstash/Elasticsearch/Kibana).

## Architecture

```
Endpoints (servers, workstations)
        │
        ▼
  Wazuh Agents              ← (Windows/Linux)
        │  (AES-encrypted, ports 1514/1515)
        ▼
  Wazuh Manager              
        │  writes /var/ossec/logs/alerts/alerts.json
        ▼
  Filebeat                    
        │  output.redis → RPUSH to list
        ▼
┌─────────────────────────────────────────────────────────┐
│  YOUR EXISTING REDIS         ← Buffer (plain LIST,     │
│  (port 6379)                   not Streams — see below) │
└─────────────────┬───────────────────────────────────────┘
                  │  BRPOP
                  ▼
┌ ─ ─ ─ ─ ─ ─ docker-compose ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┐
│                                                         │
│  Logstash       → parse, enrich, tag                    │
│       │                                                 │
│       ▼                                                 │
│  Elasticsearch  → index, search (security enabled)      │
│       │                                                 │
│       ▼                                                 │
│  Kibana         → dashboards, visualizations            │
│                                                         │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

## Quick Start (5 minutes)

**Prerequisites:**
- Docker & Docker Compose installed
- A Redis container already running on port 6379 (with auth enabled)

```bash
# 1. Clone and configure
git clone https://github.com/YOUR_USERNAME/soc-scale.git
cd soc-scale
cp .env.example .env
# Edit .env — set REDIS_PASSWORD and ELASTIC_PASSWORD (strong, unique passwords)

# 2. Start the pipeline
docker compose up -d

# 3. Verify everything is healthy
docker compose ps
# All services should show "healthy" or "running"

# 4. Test end-to-end — push a fake alert into Redis
redis-cli -a YOUR_REDIS_PASSWORD RPUSH wazuh-alerts '{"timestamp":"2026-01-01T12:00:00+0000","rule":{"level":5,"id":"100001","description":"Test alert"},"agent":{"name":"test-host","ip":"10.0.0.1"},"data":{"srcip":"8.8.8.8"}}'

# 5. Verify it landed in Elasticsearch
curl -s -u elastic:YOUR_ELASTIC_PASSWORD http://localhost:9200/wazuh-alerts-*/_search?pretty

# 6. Open Kibana
# Navigate to http://localhost:5601
# Create an index pattern for "wazuh-alerts-*" → see your test event in Discover
```

## Current State

- A **transport and indexing layer** for Wazuh security alerts
- Uses Redis as a **durable buffer** so Logstash/ES downtime doesn't lose events (Filebeat retries)
- Security defaults baked in: Elasticsearch auth, Redis auth, `noeviction` memory policy
- Designed to be the backbone you build detection rules and dashboards on top of

## Future State

- **Complete Wazuh deployment.** The Wazuh Manager and Agents will be configured ,this project picks up *after* alerts are written to `alerts.json`
- **Not production-hardened out of the box.** TLS within the Docker network is disabled for dev simplicity. Single-node Elasticsearch. No HA or clustering
- **Not horizontally scalable as-is.** Docker Compose = single host. Kubernetes/Helm is on the roadmap for v2
- **Not a replacement for Wazuh's built-in indexer.** Wazuh ships its own OpenSearch-based indexer. This project uses the standard Elastic stack instead, which gives you the full Kibana ecosystem

## Components

| Service | Image | Purpose | Port |
|---|---|---|---|
| Elasticsearch | `elasticsearch:8.17.0` | Index & search alerts | 9200 |
| Logstash | `logstash:8.17.0` | Drain Redis, parse, enrich, index | — |
| Kibana | `kibana:8.17.0` | Dashboards & visualization | 5601 |
| Redis | *local, external* | Buffer between Filebeat and Logstash | 6379 |

## Why Redis Lists (Not Streams)?

Redis Streams are technically superior (consumer groups, ack/retry, pending lists). But:
- Filebeat's `output.redis` only supports `list` (RPUSH) or `channel` (pub/sub) — no stream support
- Logstash's `redis` input only supports `list`, `channel`, `pattern_channel` — a [GitHub feature request](https://github.com/elastic/beats/issues/9868) from 2019 was never implemented
- **Consequence:** BRPOP removes an item the instant it's read. If Logstash crashes mid-processing, that event is lost. This is accepted for v0.1.0

## Configuration

All configuration is via environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `REDIS_HOST` | `host.docker.internal` | Your Redis host |
| `REDIS_PORT` | `6379` | Your Redis port |
| `REDIS_PASSWORD` | — | Redis auth password |
| `ELASTIC_PASSWORD` | — | Elasticsearch `elastic` user password |
| `ES_VERSION` | `8.17.0` | Elasticsearch image version |
| `LS_VERSION` | `8.17.0` | Logstash image version |
| `KIBANA_VERSION` | `8.17.0` | Kibana image version |

## Logstash Pipeline

The Logstash pipeline ([`logstash/pipeline/logstash.conf`](logstash/pipeline/logstash.conf)) does:

1. **Input:** BRPOP from Redis list `wazuh-alerts`
2. **Filter:**
   - Normalizes `@timestamp` from Wazuh's event timestamp
   - Tags events with `source_type: wazuh`
   - GeoIP enrichment on source IPs
   - Strips Filebeat envelope metadata
3. **Output:** Indexes into `wazuh-alerts-YYYY.MM.dd` in Elasticsearch

## Known Limitations

- **Filebeat ↔ Redis 7.x compatibility:** Filebeat's Redis output is officially tested against Redis 3.2.4–5.0.8. Redis 7.x works in practice but isn't in Elastic's test matrix
- **No TLS inside Docker network:** HTTP between Logstash/Kibana and Elasticsearch is unencrypted (auth is still required). Enable `xpack.security.http.ssl.enabled` for production
- **Single-node Elasticsearch:** No replica shards, no failover. Acceptable for dev/lab, not for production
- **Memory pressure:** Without monitoring Redis queue length, a stalled Logstash lets the Redis list grow until `maxmemory` is hit and writes are rejected

## Roadmap

- [ ] **v0.1.0** — Current: Redis → Logstash → ES → Kibana (single source)
- [ ] **v0.2.0** — Add CloudTrail as a second log source (separate Redis key, unified Kibana view)
- [ ] **v1.0.0** — Production hardening (TLS, Elasticsearch clustering, Redis Sentinel)
- [ ] **v2.0.0** — Kubernetes/Helm chart

## License

[MIT](LICENSE)
