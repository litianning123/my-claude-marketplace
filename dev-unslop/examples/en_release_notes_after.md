# Release v2.4.0

## Bug Fixes

- Fixed a race condition in the span processor that caused intermittent data loss under high concurrency (10k+ spans/sec). Cache invalidation and batch commit weren't atomic — concurrent workers could interleave between the two, dropping spans that arrived during the window. Batched both operations under a single write lock.
- Fixed a memory leak in the metrics exporter — histogram buckets weren't cleaned up after metric expiry.

## New: Probabilistic trace sampling

Sampling rate now self-adjusts based on per-endpoint traffic volume. Hot endpoints sample at 1%; cold endpoints at 100%. Replaces the previous fixed 10% global rate. p99 trace ingestion latency dropped from 120ms to 50ms in pre-release load tests.

## New: gRPC streaming transport (UDP deprecated)

The legacy UDP transport is deprecated and will be removed in v3.0. Switch to gRPC streaming by setting `collector.transport: grpc` in your config.
