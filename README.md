# Hardware Deal Finder

Hardware Deal Finder is a reusable deal-intelligence engine for discovering hardware that
meets configurable requirements, explaining its ranking, and retaining price observations.
The included profile targets three identical mini PCs for a Talos/Kubernetes homelab, but the
domain and provider interfaces are not tied to mini PCs.

Version 0.2 includes validated YAML configuration, provenance-backed enrichment, hard filtering,
weighted scoring, multi-seller cluster allocation, SQLite snapshots and price history,
table/JSON/CSV reporting, watch-event detection, provider and notification plugin interfaces,
an eBay Browse API adapter, a configurable documented-JSON-feed adapter, and explicit researched
access states for the other trusted marketplaces. It also ships a non-root container, CI, and a
hardened Kubernetes CronJob.

## Architecture

```text
YAML + CLI overrides
        |
        v
SearchService ---- async ----> HardwareProvider plugins / package entry points
        |                         | eBay Browse API
        |                         | generic documented JSON feeds
        |                         | fixture/test and researched unsupported states
        v
normalize -> enrich -> deduplicate -> hard filter -> score -> cluster allocation
        |
        +----> SQLite snapshots / observations -> watch comparison -> notifications
        +----> table / JSON / CSV / detail / price history
```

Providers return the marketplace-neutral `HardwareListing` model. The orchestrator only knows
the `HardwareProvider` abstraction, so provider failures and marketplace-specific parsing stay
at the boundary. Dependencies for enrichment, filtering, scoring, and persistence are injected.
Provider construction is driven by `sites.yaml` and a registry rather than conditionals in the
search service. Third-party packages can expose factories under the `dealfinder.providers`
entry-point group. A single implementation can also be aliased under multiple configured site
names.

Unknown data is deliberately different from a negative value. An explicit `tpm_2=false`, for
example, fails a TPM requirement; missing TPM information remains eligible with a prominent
“verify before purchase” warning. This avoids inventing capabilities while still making sparse
marketplace data useful.

## Install

Requirements: Python 3.12+ and [`uv`](https://docs.astral.sh/uv/).

```bash
uv sync --extra dev
uv run dealfinder --help
```

No secrets are stored in the repository. To query eBay, create production credentials for the
eBay Browse API and export:

```bash
export EBAY_CLIENT_ID='...'
export EBAY_CLIENT_SECRET='...'
```

Without credentials, eBay reports `unavailable` and the run completes normally. Tests use a
mock HTTP transport and never call a live marketplace.

## Usage

```bash
uv run dealfinder search
uv run dealfinder search --provider ebay --top 10
uv run dealfinder search --max-price 300 --quantity 3
uv run dealfinder search --cpu 'Ryzen 5 PRO 5650GE'
uv run dealfinder search --format json
uv run dealfinder search --format csv
uv run dealfinder show 1
uv run dealfinder history ebay 'v1|123|0' --format json
uv run dealfinder watch --format json
```

Use a different profile or site policy without changing Python:

```bash
uv run dealfinder search --config /config/nas.yaml --sites /config/sites.yaml
```

Search results default to `data/dealfinder.db`. For Kubernetes or another container runtime,
mount persistent storage and set either `DEALFINDER_STATE_PATH` or `--state`:

```bash
DEALFINDER_STATE_PATH=/state/dealfinder.db uv run dealfinder watch --format json
```

The CLI exits successfully when individual providers are unavailable and includes diagnostics
for every enabled provider. Configuration and credential paths do not assume an interactive
workstation.

## Configuration

[`config/search.yaml`](config/search.yaml) contains the homelab profile. It separates:

- hard requirements: maximum delivered price, minimum specifications, explicit unsupported
  security features, disallowed conditions/sellers, excluded text, and known insufficient
  quantity;
- preferences: preferred price/CPU, desired RAM and storage, upgradeability, enterprise
  features, faster networking, seller quality, and warranty/returns;
- scoring weights, which must sum to `1.0`;
- RAM and NVMe upgrade prices, keyed by capacity.
- watch thresholds for new strong deals and material price drops.

[`config/sites.yaml`](config/sites.yaml) controls implementation/alias, enablement, trust
multiplier, timeout, request rate, retry count, response cache, listing limit, and arbitrary
provider-specific settings. Amazon, Newegg, Minisforum, Lenovo, Dell, HP, and Back Market remain
disabled because the August 2026 access audit found no suitable public consumer deal-search API.
When enabled they return `unsupported` with a provider-specific reason and reference.

Any number of explicitly authorized documented JSON feeds can reuse the generic adapter:

```yaml
sites:
  internal_catalog:
    provider: generic
    enabled: true
    settings:
      endpoint: https://catalog.example.com/search
      query_parameter: query
      items_path: results
      headers_from_env: {Authorization: CATALOG_AUTHORIZATION}
      field_map:
        id: sku
        title: name
        url: link
        price: offer.price
        shipping: offer.shipping
        quantity: stock
```

CLI values override only the loaded in-memory configuration. The source YAML is never edited.

## Scoring and costs

Every category receives a `0–100` subscore and is multiplied by its YAML weight. The final score
and explanation are retained with the observation. Provider trust is applied as a transparent
final multiplier. Price means item plus shipping; taxes are not estimated because location is
not currently part of the search model.

Upgrade estimates are per node and use configured capacity prices. The detailed model exposes
delivered unit price, upgrade cost, required-quantity total, score categories, warnings, and
missing information. Compatible partial listings are allocated cheapest-first into complete
cluster plans without mixing CPU/RAM/storage/condition configurations. Upgrade compatibility
still needs verification before purchase.

## Persistence

SQLite uses three future-friendly tables:

- `listings`: stable provider identity and first/last seen timestamps;
- `search_runs`: a reconstructable complete result, provider diagnostics, and cluster plans;
- `observations`: append-only price, shipping, availability, score, rank, and reconstructable
  normalized snapshot.

The `history` command exposes observations. `watch` compares the latest result to the previous
snapshot and emits new strong deals or price drops through a notification plugin. The built-in
console channel is suitable for logs and CronJobs; external channels remain separate plugins.

## Container and Kubernetes

Build and run with ephemeral state:

```bash
docker build -t hardware-deal-finder .
docker run --rm --tmpfs /state:rw,uid=65532,gid=65532,mode=0700 \
  hardware-deal-finder
```

The image runs as UID/GID `65532`, installs only locked production dependencies, and defaults to
a one-shot JSON `watch`. [`deploy/kubernetes/cronjob.yaml`](deploy/kubernetes/cronjob.yaml)
provides a daily CronJob and PVC. Replace the example image tag with an immutable published tag
or digest. Optionally create `hardware-deal-finder-credentials` containing eBay credentials;
the secret reference is optional, so missing credentials produce diagnostics rather than a
failed Pod.

```bash
kubectl create secret generic hardware-deal-finder-credentials \
  --from-literal=EBAY_CLIENT_ID='...' \
  --from-literal=EBAY_CLIENT_SECRET='...'
kubectl apply -f deploy/kubernetes/cronjob.yaml
```

## Adding a provider

See [`docs/provider-development.md`](docs/provider-development.md). In short:

1. subclass `HardwareProvider`;
2. keep HTTP/authentication and payload parsing inside the adapter;
3. normalize every result into `HardwareListing`;
4. register a built-in factory or publish a `dealfinder.providers` entry point;
5. mock all HTTP responses in provider tests;
6. document credentials, rate limits, terms, and unsupported states.

The central `SearchService`, filtering, scoring, and reporting code should not change.

## Development

```bash
make verify
# equivalent to:
uv run --extra dev ruff check .
uv run --extra dev mypy src
uv run --extra dev pytest
```

The codebase uses strict mypy, Ruff, pytest, Pydantic, `Decimal` for money, asynchronous HTTP,
and standard logging. Each feature has offline tests, including OAuth/API response mocking and
provider failure isolation.

## Access and scraping policy

The current real provider uses eBay's documented API. The project does not bypass CAPTCHAs,
anti-bot systems, authentication controls, fingerprints, robots directives, or rate limits. A
site without a safe and reliable integration returns an explicit `unsupported` status. Before
adding any HTML adapter, review the site's current terms and `robots.txt`, identify the crawler,
rate-limit requests, cache where appropriate, parse defensively, and fail closed when access is
disallowed or markup becomes unreliable.

## Current limitations and risks

- eBay Browse API access and OAuth credentials are required for live results; eligibility,
  quotas, response fields, and marketplace policies can change.
- Marketplace titles are incomplete. Enrichment covers a small audited CPU/machine map, records
  source/confidence/reference, and never treats inference as manufacturer confirmation.
- Quantity is often missing. Missing quantity is warned about; known insufficient quantity is a
  hard rejection.
- Taxes, region-specific delivery constraints, cross-configuration bundles, and upgrade
  compatibility are not yet modeled.
- Non-eBay trusted marketplaces are researched unsupported adapters, not scrapers. See
  [`docs/access-research.md`](docs/access-research.md).
- The console notification channel is implemented; external delivery channels are intentionally
  left to plugins so the core stores no vendor credentials.
