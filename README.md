# tak-feeder-nysse

TAK Feeder for Nysse (Tampere public transport) bus data.
(C) 2026 Stefan Gofferje

Re-implementation of my Node-RED flow for pulling real-time bus traffic data and creating TAK CoTs.

## Configuration

Configurable via environment variables:

- `COT_URL`: TAK server URL (e.g., `ssl://takserver:8089` or `udp://239.2.3.1:6969`).
- `CLIENT_CERT`: Path to user certificate for mTLS.
- `CLIENT_KEY`: Path to user key for mTLS.
- `PYTAK_TLS_DONT_VERIFY`: Set to `1` to skip TLS verification.
- `NYSSE_LINE_FILTER`: Comma-separated list of bus route numbers to filter (e.g., `60,64`).
- `UPDATE_INTERVAL`: Polling interval in seconds (default: `3`).

## Usage

### Docker

```bash
docker run -d \
  --name tak-feeder-nysse \
  -e COT_URL=udp://239.2.3.1:6969 \
  -e NYSSE_LINE_FILTER=60,64 \
  ghcr.io/sgofferj/tak-feeder-nysse:latest
```

### Docker Compose

```yaml
version: '3'
services:
  tak-feeder-nysse:
    image: ghcr.io/sgofferj/tak-feeder-nysse:latest
    restart: always
    environment:
      - COT_URL=udp://239.2.3.1:6969
      - NYSSE_LINE_FILTER=60,64
      - UPDATE_INTERVAL=3
```

## License

This project is licensed under the terms of the GNU General Public License v3.0. See [LICENSE.md](LICENSE.md) for details.
