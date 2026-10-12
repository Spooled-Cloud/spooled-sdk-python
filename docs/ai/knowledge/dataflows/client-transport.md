# Transport

- Defaults in `src/spooled/config.py`.
- REST and gRPC create/enqueue omit unset retry/timeout values so backend queue/server defaults apply; explicit values are still sent.
- gRPC unary calls use the configured per-call timeout; long-lived streams default to no deadline unless `stream_timeout` is set, and stream deadline errors preserve the configured stream timeout in `TimeoutError.timeout_seconds`.
- Ingest: custom only (no GitHub/Stripe helpers).
- Realtime WS/SSE envelopes are objects `{type, data}`. A non-object JSON frame is dropped; `RealtimeEvent.data` accepts any JSON so a non-object `data` field cannot ValidationError and tear down the connection.
- REST bearer is the API key (or access token) for the life of the client. `get_jwt_token()` only feeds the realtime transport (cached, renewed ~60 s before `exp`); it must never call `HttpClient.set_auth_token`. A configured `access_token` + `refresh_token` is renewed through the HTTP client's single-flight refresh.
- Token refresh is single-flight: concurrent 401s wait on one lock/refresh and replay with the new token; the refresh call's own request is the only one that skips the refresh (thread-local / ContextVar guard).
- SSE streams use `SSE_TIMEOUT` (read 60 s; server keep-alive 15 s), check the HTTP status (`stream_error`), stop on non-retryable errors (401/403/404), restore the retry counter only when an event arrives, and end a job stream after its terminal status. The unified SSE client reconnects on a clean end and gives up (`last_error` + `error` event) on a rejected token.
- `with_options()` goes through `config.merge_client_config`, which carries every field; `ws_url` is carried only when it was set explicitly.

- Every response's `X-RateLimit-*` headers are parsed in `_execute_request` (sync and async) into `HttpClient.rate_limit` / `AsyncHttpClient.rate_limit` (`RateLimitInfo`, last writer wins across threads), before error mapping, so a 429 updates it too.
- `request(..., with_headers=True)` / `get(..., with_headers=True)` return `(body, response headers)`; list resources use it for `X-Has-More`. The default return value is unchanged.
- gRPC stubs are generated with the locked `grpcio-tools` (1.80.0, protobuf gencode 6.31.1) by `scripts/generate_grpc.sh`; `proto/spooled.proto` is a copy of `spooled-backend/proto/spooled.proto`.
