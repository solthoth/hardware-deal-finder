# Provider development guide

## Contract

Implement `dealfinder.providers.base.HardwareProvider` and its asynchronous `search(criteria)`
method. Return normalized `HardwareListing` objects. Raise `ProviderUnavailable` for missing
credentials, disallowed access, maintenance, or incompatible responses, and
`ProviderRateLimited` after a bounded retry budget. Raise `ProviderUnsupported` when no safe
documented integration exists. Do not leak marketplace response models into the service or
domain logic.

## Implementation checklist

1. Confirm a documented API/feed exists and review current terms, quotas, and authentication.
2. Add a small adapter module under `dealfinder.providers`.
3. Accept `SiteConfig`; use `ResilientHttpClient` to honor timeout, rate limiting, bounded
   retries/backoff, response caching, identification, and async connection pooling.
4. Read secrets from provider-specific environment variables. Never add them to YAML, fixtures,
   logs, URLs, or exceptions.
5. Keep authentication, retries/backoff, HTTP status mapping, and response parsing in focused
   methods.
6. Map responses through provider-local parsing and shared normalization into
   `HardwareListing`. Preserve raw data only for diagnostics; do not use it in central logic.
7. For a built-in adapter, decorate a factory with `register_provider("name")` and import its
   module from the provider package. For an external package, publish the factory as an entry
   point instead:

   ```toml
   [project.entry-points."dealfinder.providers"]
   vendor = "vendor_package.provider:build_provider"
   ```

   A factory accepts `SiteConfig` and returns `HardwareProvider`.
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

Registration is intentionally separate from orchestration. External providers require only an
installed entry point and YAML. Built-ins may extend composition imports and YAML, but neither
path may add marketplace branches to `SearchService`, filtering, scoring, persistence, or
reporting. Use `provider: generic` aliases when several trusted sites share documented JSON-feed
semantics.
