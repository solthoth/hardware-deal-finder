"""Command-line interface for searches and persisted result details."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from collections.abc import Sequence
from contextlib import suppress
from decimal import Decimal
from pathlib import Path

from dealfinder.config import SearchConfig, SitesConfig, load_search_config, load_sites_config
from dealfinder.notifications import create_notification_provider
from dealfinder.persistence import SQLiteRepository
from dealfinder.providers import create_enabled_providers
from dealfinder.reporting import (
    render_csv,
    render_detail,
    render_json,
    render_price_history,
    render_table,
)
from dealfinder.service import SearchRun, SearchService
from dealfinder.watch import detect_deal_events

DEFAULT_STATE = Path(os.getenv("DEALFINDER_STATE_PATH", "data/dealfinder.db"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dealfinder")
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="search enabled marketplaces")
    search.add_argument("--config", default="config/search.yaml")
    search.add_argument("--sites", default="config/sites.yaml")
    search.add_argument("--provider", action="append")
    search.add_argument("--max-price", type=Decimal)
    search.add_argument("--cpu")
    search.add_argument("--quantity", type=int)
    search.add_argument("--top", type=int, default=20)
    search.add_argument("--format", choices=["table", "json", "csv"], default="table")
    search.add_argument("--state", type=Path, default=DEFAULT_STATE)
    watch = commands.add_parser("watch", help="search once and emit new or improved deals")
    watch.add_argument("--config", default="config/search.yaml")
    watch.add_argument("--sites", default="config/sites.yaml")
    watch.add_argument("--provider", action="append")
    watch.add_argument("--max-price", type=Decimal)
    watch.add_argument("--cpu")
    watch.add_argument("--quantity", type=int)
    watch.add_argument("--top", type=int, default=20)
    watch.add_argument("--format", choices=["table", "json"], default="table")
    watch.add_argument("--notify", default="console")
    watch.add_argument("--state", type=Path, default=DEFAULT_STATE)
    show = commands.add_parser("show", help="show a ranked result from the latest search")
    show.add_argument("rank", type=int)
    show.add_argument("--run-id", type=int)
    show.add_argument("--state", type=Path, default=DEFAULT_STATE)
    history = commands.add_parser("history", help="show observed price history for a listing")
    history.add_argument("provider")
    history.add_argument("listing_id")
    history.add_argument("--format", choices=["table", "json"], default="table")
    history.add_argument("--state", type=Path, default=DEFAULT_STATE)
    return parser


def apply_overrides(config: SearchConfig, args: argparse.Namespace) -> SearchConfig:
    updated = config.model_copy(deep=True)
    if args.max_price is not None:
        updated.search.price.max_per_unit = args.max_price
        updated.search.price.preferred_max = min(updated.search.price.preferred_max, args.max_price)
    if args.quantity is not None:
        updated.search.quantity_required = args.quantity
    if args.cpu:
        updated.search.cpu.preferred_models = [args.cpu]
        updated.search.query = args.cpu
    return updated


def _select_sites(config: SitesConfig, names: list[str] | None) -> SitesConfig:
    if not names:
        return config
    missing = set(names).difference(config.sites)
    if missing:
        raise ValueError(
            f"providers not present in site configuration: {', '.join(sorted(missing))}"
        )
    selected = {
        name: site.model_copy(update={"enabled": name in names})
        for name, site in config.sites.items()
    }
    return config.model_copy(update={"sites": selected})


async def _search(args: argparse.Namespace) -> tuple[SearchRun, SearchConfig]:
    config = apply_overrides(load_search_config(args.config), args)
    sites = _select_sites(load_sites_config(args.sites), args.provider)
    repository = SQLiteRepository(args.state)
    service = SearchService.from_config(config, create_enabled_providers(sites), store=repository)
    run = await service.search()
    run.ranked = run.ranked[: args.top]
    return run, config


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        if args.command == "show":
            print(render_detail(SQLiteRepository(args.state).load_rank(args.rank, args.run_id)))
            return 0
        if args.command == "history":
            history = SQLiteRepository(args.state).price_history(args.provider, args.listing_id)
            print(render_price_history(history, args.format))
            return 0
        previous = None
        if args.command == "watch":
            with suppress(LookupError):
                previous = SQLiteRepository(args.state).load_run()
        run, config = asyncio.run(_search(args))
    except (ValueError, LookupError, OSError) as error:
        parser.error(str(error))
    if args.command == "watch":
        events = detect_deal_events(
            run,
            previous,
            minimum_score=config.watch.minimum_score,
            minimum_price_drop_percent=config.watch.minimum_price_drop_percent,
        )
        notifier = create_notification_provider(args.notify, args.format)
        asyncio.run(notifier.notify(events))
        return 0
    if args.format == "table":
        output = render_table(run, config.search)
    elif args.format == "json":
        output = render_json(run)
    else:
        output = render_csv(run)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
