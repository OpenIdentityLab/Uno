# UNO Layer1 (Go)

Minimal Layer 1 consensus node prototype (libp2p + Gossipsub + mDNS).

## Files

- `main.go` — boots the node, joins Gossipsub, logs `node ready`
- `node.go` — node runtime (libp2p host, topics, mDNS discovery)
- `block.go` — `Block` and `Event` structures
- `vrf.go` — HKDF-SHA256 based VRF helpers
- `round.go` — round logic (VRF producer/verifier selection, votes, finalize on 2/3)
- `consensus.go` — HotStuff-lite 2 phases (PREPARE -> COMMIT)

## Build

```bash
cd /tmp/uno_clone/layer1
export PATH=/opt/homebrew/bin:$PATH
go build ./...
```

## Local test (2 nodes, mDNS discovery)

Terminal A:

```bash
cd /tmp/uno_clone/layer1
export PATH=/opt/homebrew/bin:$PATH
go run . -port 9101
```

Terminal B:

```bash
cd /tmp/uno_clone/layer1
export PATH=/opt/homebrew/bin:$PATH
go run . -port 9102
```

Expected logs:

- Both nodes print `node ready`
- Each node eventually logs `mdns peer discovered: ...`
- `connected peers: 1` appears on both

No static seed configuration is required for this LAN test.
