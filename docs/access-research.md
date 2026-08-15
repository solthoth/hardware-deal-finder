# Marketplace access research

Last reviewed: 2026-08-15. Access contracts and site policies change; re-check the linked primary
sources before replacing an unsupported adapter.

| Provider | Current integration decision | Primary source |
| --- | --- | --- |
| eBay | Supported through OAuth client credentials and the Browse API. | [eBay Buy APIs](https://developer.ebay.com/api-docs/buy/static/buy-landing.html) |
| Amazon | Unsupported pending a stable configured Creators API contract. PA-API was deprecated May 15, 2026 and its official docs direct users to Creators API. | [Amazon PA-API migration notice](https://webservices.amazon.com/paapi5/documentation/troubleshooting/sign-up-as-an-associate.html) |
| Newegg | Unsupported for consumer deal search. Its documented Marketplace API is for registered sellers managing items, orders, accounts, and reports. | [Newegg Marketplace API](https://developer.newegg.com/newegg_marketplace_api/) |
| Minisforum | Unsupported: no documented public product-search/catalog API was found. | [Minisforum store](https://store.minisforum.com/) |
| Lenovo Outlet | Unsupported: no documented public Outlet search API was found; global robots rules disallow internal search URLs. | [Lenovo robots.txt](https://www.lenovo.com/robots.txt) |
| Dell Outlet / Refurbished | Unsupported for public deal search. Dell documents a Premier Catalog API for enabled B2B customer catalogs, not a public Outlet search API. | [Dell Developer APIs](https://developer.dell.com/apis) |
| HP store/refurbished | Unsupported: no documented public consumer search API was found; robots rules disallow store API and search paths. | [HP robots.txt](https://www.hp.com/robots.txt) |
| Back Market | Unsupported: no documented public consumer catalog search API was found. | [Back Market](https://www.backmarket.com/) |

`ProviderUnsupported` is deliberate, not an unfinished scraping stub. It keeps automation honest
and lets operators distinguish a policy/access limitation from a transient outage or rate limit.
An operator with access to a documented HTTPS JSON feed can configure the generic provider; an
operator with a marketplace-specific documented API can install a provider entry-point package.

