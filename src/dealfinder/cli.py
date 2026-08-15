"""Command-line interface for searches and persisted result details."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from collections.abc import Sequence
from decimal import Decimal
from pathlib import Path

from dealfinder.config import SearchConfig, SitesConfig, load_search_config, load_sites_config
from dealfinder.persistence import SQLiteRepository
from dealfinder.providers import create_enabled_providers
from dealfinder.reporting import render_csv, render_detail, render_json, render_table
from dealfinder.service import SearchRun, SearchService

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
    show = commands.add_parser("show", help="show a ranked result from the latest search")
    show.add_argument("rank", type=int)
    show.add_argument("--run-id", type=int)
    show.add_argument("--state", type=Path, default=DEFAULT_STATE)
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
        run, config = asyncio.run(_search(args))
    except (ValueError, LookupError, OSError) as error:
        parser.error(str(error))
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
