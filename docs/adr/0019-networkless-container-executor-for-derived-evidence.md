# A networkless container may produce derived evidence through a bounded queue

ADR-0011 is superseded. Alpha Desk now exposes `run_python` for small arithmetic
over explicit JSON inputs. The model does not execute inside `api`: a separate
`executor` service receives atomic JSON files through a named volume, starts an
isolated Python child, and returns JSON through the same queue.

The service has no network namespace, runs as UID/GID 65534, has a read-only root
filesystem, drops every Linux capability, forbids privilege escalation, and uses
bounded tmpfs, CPU, memory, process, wall-clock, input, and output resources. It
receives no source mount, database credential, application environment, or Docker
socket. The API accepts only JSON output and labels it **Derived Evidence**.

## Evidence boundary

Successful execution proves only that the submitted arithmetic produced the shown
result in the isolated worker. It does not register a method, establish data
provenance, or satisfy the Recommendation Gate. A recommendation, reference price,
or price zone still needs suitable registered evidence from the Tool Catalog.

The executor is optional. When disabled or unavailable, `run_python` is absent from
the model-visible catalog rather than present as a broken promise. Calls that do run
count against the Turn's shared external-call budget.

## Considered options

- In-process `exec`, RestrictedPython, and a stripped `__builtins__` were rejected
  because they do not create an operating-system security boundary.
- Giving `api` the Docker socket was rejected because compromise of the application
  would become control of the host Docker daemon.
- Per-call containers under gVisor were not selected. The current development and
  Compose targets cannot exercise `runsc` consistently, so this ADR makes no gVisor
  claim.
- A managed microVM service would provide a stronger isolation and incident-response
  boundary, but adds an external dependency and cost that current demand does not
  justify.

## Residual risk

This is process and container isolation, not a virtual-machine sandbox. Kernel or
container-runtime escapes remain possible; resource limits can reduce denial of
service but cannot prove arbitrary code safe. Operators must keep the base image and
runtime patched, leave the service networkless and unprivileged, and disable the
feature if the deployment cannot preserve these Compose constraints. Opening this
capability to untrusted public users requires a new decision for stronger isolation.

## Consequences

- `docker-compose.yml` has a fifth default service and one named queue volume.
- The executor protocol is deliberately small: `code`, JSON `inputs`, and one JSON
  `result`; files and plots are outside the contract.
- Derived results remain auditable as citations but unsuitable as the sole basis for
  an investment recommendation.
