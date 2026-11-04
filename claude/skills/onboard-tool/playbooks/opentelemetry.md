# Playbook: opentelemetry

Zero-code (automatic) OpenTelemetry instrumentation for an existing Python
service. Sends traces, metrics, and logs to any OTLP backend (an
OpenTelemetry Collector, or a vendor that accepts OTLP) without changing
application code.

## Applies when
- A Python service using a framework with an OpenTelemetry instrumentation
  library (for example Flask, Django, FastAPI, requests).
- Not for other languages: say this playbook covers Python only and ask for
  the official docs for that language.
- If the user wants manual spans or custom metrics, say that is code
  instrumentation, outside this playbook, and ask before planning it.

## Detect
- `opentelemetry-*` packages already in the manifest or lock file.
- `opentelemetry-instrument` already in a start command (Procfile,
  Dockerfile `CMD`, Makefile, scripts).
- `OTEL_*` variables in env files, CI, or deployment config.
- Another APM agent already wrapping the start command. Two agents on one
  process is a conflict: surface it and ask.

## Prerequisites
- Where telemetry should go: an OTLP endpoint. Without one, plan the
  console exporter for a local check only.
- A service name the team agrees on.
- If the backend needs an auth header, the user creates it as a secret in
  their secret store. Reference it by environment variable name only.

## Files
Keep the change set to these. Nothing else.

1. **Dependencies.** Add to the manifest the project already uses:
   `opentelemetry-distro` and `opentelemetry-exporter-otlp`.
2. **Instrumentation libraries.** With pip, run
   `opentelemetry-bootstrap -a install`. It reads the active environment
   and installs the matching instrumentation package for each installed
   library (for Flask, `opentelemetry-instrumentation-flask`). Run
   `opentelemetry-bootstrap` with no arguments first to list what it would
   install, and show that list in the plan. With uv, use
   `uv run opentelemetry-bootstrap -a requirements | uv add --requirement -`
   instead, because the official docs warn that `-a install` under uv can
   produce broken dependency setups.
3. **Start command.** Wrap the existing command, for example
   `opentelemetry-instrument python app.py`.
4. **Configuration as environment variables** (where the project already
   keeps runtime config, never hard-coded in source):
   - `OTEL_SERVICE_NAME`: required in practice. Default is `unknown_service`.
   - `OTEL_EXPORTER_OTLP_ENDPOINT`: default `http://localhost:4317` (gRPC)
     or `http://localhost:4318` (HTTP).
   - `OTEL_EXPORTER_OTLP_PROTOCOL`: `grpc` or `http/protobuf`. The spec
     also defines `http/json`; check the exporter supports it before using it.
   - `OTEL_TRACES_EXPORTER`, `OTEL_METRICS_EXPORTER`, `OTEL_LOGS_EXPORTER`:
     default `otlp`. Use `none` to turn a signal off.
   - `OTEL_EXPORTER_OTLP_HEADERS`: only if the backend needs auth, set
     from a secret, never committed.
   - Optional: `OTEL_RESOURCE_ATTRIBUTES` (for example
     `deployment.environment=staging`).

## Caveats to put in the plan's risks
- **Flask debug reloader.** `debug=True` turns on the reloader, which
  breaks instrumentation. Run with `use_reloader=False` when debugging.
- **Pre-fork servers.** With gunicorn or uvicorn using more than one
  `--workers`, auto-instrumentation can break metrics. Options from the
  docs: one worker, gunicorn with `uvicorn.workers.UvicornWorker` for ASGI,
  or initialize instrumentation in a `post_fork` hook.
- **Build dependencies.** Some packages need a compiler on slim images
  (`build-essential` and `python3-dev` on Debian or Ubuntu).
- **Re-running bootstrap.** Instrumentation packages track installed
  libraries, so re-run bootstrap after adding a library, ideally in the
  build.

## Validation
Run locally with the console exporter and send one request:

```bash
opentelemetry-instrument --traces_exporter console --metrics_exporter none --logs_exporter none python app.py
# in another shell
curl -s http://localhost:<port>/<route>
```

Success: the service console prints span JSON with `kind` set to
`SpanKind.SERVER` and the route in its attributes. Then point
`OTEL_EXPORTER_OTLP_ENDPOINT` at the real collector and confirm the
service appears in the backend under `OTEL_SERVICE_NAME`.

## Rollback
Remove the two dependencies and the bootstrap-installed
`opentelemetry-instrumentation-*` packages, restore the original start
command, and delete the `OTEL_*` variables.

## Never
- Commit endpoint credentials or auth headers.
- Install a vendor agent alongside OpenTelemetry on the same process.
- Change application code for this playbook.

## Official docs
- https://opentelemetry.io/docs/zero-code/python/
- https://opentelemetry.io/docs/zero-code/python/configuration/
- https://opentelemetry.io/docs/zero-code/python/troubleshooting/
- https://opentelemetry.io/docs/languages/sdk-configuration/general/
- https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/
