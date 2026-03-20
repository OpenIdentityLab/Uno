# Examples

This directory contains pre-built example bundles and state snapshots for reference.

All example files are **regenerable** from scratch. The `.pem` private key files are excluded from the repository (see `.gitignore`) — they are throwaway demo keys and must not be committed.

## Regenerate

```bash
python3 runtime/uno_runtime.py build-demo \
  --output examples/demo_bundle.json \
  --witnessed-output examples/demo_bundle_witnessed.json \
  --build-manifest-output examples/demo_build_manifest.json
```

This rebuilds `demo_bundle.json`, `demo_bundle_witnessed.json`, `demo_build_manifest.json`, and repopulates `demo_state/` and `demo_witness_state/` with fresh keys and events.

For the manual witness flow, see [`README_RUN.md`](../README_RUN.md).
