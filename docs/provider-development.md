# Provider development guide

## Contract

Implement `dealfinder.providers.base.HardwareProvider` and its asynchronous `search(criteria)`
method. Return normalized `HardwareListing` objects. Raise `ProviderUnavailable` for missing
credentials, disallowed access, maintenance, or incompatible responses, and
`ProviderRateLimited` after a bounded retry budget. Do not leak marketplace response models into
the service or domain logic.

## Implementation checklist

1. Confirm a documented API/feed exists and review current terms, quotas, and authentication.
2. Add a small adapter module under `dealfinder.providers`.
3. Accept `SiteConfig`; honor timeout, maximum listings, provider settings, and applicable rate
   limits. Identify the client and use async connection pooling.
4. Read secrets from provider-specific environment variables. Never add them to YAML, fixtures,
   logs, URLs, or exceptions.
5. Keep authentication, retries/backoff, HTTP status mapping, and response parsing in focused
   methods.
6. Map responses through provider-local parsing and shared normalization into
   `HardwareListing`. Preserve raw data only for diagnostics; do not use it in central logic.
7. Add a factory decorated with `register_provider("name")`, import the built-in module from the
   provider package, and add its policy to `config/sites.yaml`.
8. Add mocked tests for success, missing credentials, malformed/empty data, rate limiting,
   retries, and safe unavailability. Never make a live request from pytest.
9. Run `make verify` before committing.

## HTML-only sources

An HTML provider is acceptable only when current terms and `robots.txt` permit it and no official
API/feed is practical. Use BeautifulSoup with defensive selectors, a conservative configurable
request rate, caching, clear user-agent identification, and fixture HTML tests. A CAPTCHA,
challenge page, disallow rule, or material markup change must produce an unavailable status—do
not add circumvention.

## Registration boundary

Registration is intentionally separate from orchestration. Adding a provider may extend the
provider package's composition imports and YAML, but must not add marketplace branches to
`SearchService`, filtering, scoring, persistence, or reporting.
