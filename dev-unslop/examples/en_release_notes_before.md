# Release v2.4.0

In today's rapidly evolving technical landscape, application observability has become more critical than ever. We're excited to announce that v2.4.0 represents a paradigm shift in how our platform handles distributed tracing. This release leverages cutting-edge sampling algorithms to deliver unprecedented visibility into your microservices architecture, empowering teams to achieve remarkable improvements in their debugging workflows.

## What's New

- **Enhanced Performance**: Significantly improved trace ingestion pipeline that utilizes a highly optimized, robust batching mechanism
- **Seamless Integration**: Our comprehensive OpenTelemetry exporter now provides seamless interoperability with all major observability platforms
- **Game-Changing Insights**: It's not just a tracing tool, but a holistic debugging solution that transforms how you think about distributed systems
- **Extremely Intuitive UI**: Completely redesigned trace viewer that is extremely intuitive and remarkably responsive

## Bug Fixes

- Fixed a race condition in the span processor that caused intermittent data loss under high concurrency (10k+ spans/sec). The root cause was that cache invalidation and batch commit weren't atomic operations — concurrent workers could interleave between the two, dropping spans that arrived during the window. Solved by batching both operations under a single write lock.
- Addressed a memory leak in the metrics exporter by adding explicit cleanup of histogram buckets

## Migration Notes

To summarize, upgrading from v2.3.x requires updating your collector configuration. Furthermore, it is worth noting that the legacy UDP transport has been deprecated in favor of gRPC streaming. We strongly recommend planning your migration at your earliest convenience to seamlessly transition before the next major release.

In conclusion, v2.4.0 is a testament to our commitment to providing robust, enterprise-grade observability. We can't wait to see what you build with it!
