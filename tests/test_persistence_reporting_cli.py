from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from dealfinder.cli import apply_overrides, build_parser, main
from dealfinder.config import load_search_config
from dealfinder.models import HardwareListing
from dealfinder.persistence import SQLiteRepository
from dealfinder.reporting import render_csv, render_detail, render_json, render_table
from dealfinder.scoring import DealScorer
from dealfinder.service import SearchRun


def test_sqlite_keeps_observation_history(
    tmp_path: Path, search_config: object, good_listing: HardwareListing
) -> None:
    config = load_search_config("config/search.yaml")
    scorer = DealScorer(config.search, config.scoring, config.upgrade_costs)
    first = scorer.score(good_listing)
    cheaper = scorer.score(good_listing.model_copy(update={"item_price": Decimal("220")}))
    repository = SQLiteRepository(tmp_path / "history.db")
    first_run = repository.save([first])
    repository.save([cheaper])
    history = repository.price_history("fixture", "1")
    assert first_run == 1
    assert [row.total_price for row in history] == [Decimal("250"), Decimal("230")]
    assert repository.load_rank(1, first_run).listing.title == good_listing.title


def test_reporting_formats_are_machine_and_human_readable(
    search_config: object, good_listing: HardwareListing
) -> None:
    config = load_search_config("config/search.yaml")
    ranked = DealScorer(config.search, config.scoring, config.upgrade_costs).score(good_listing)
    run = SearchRun(ranked=[ranked], provider_results={})
    assert "ThinkCentre M75q" in render_table(run, config.search)
    assert json.loads(render_json(run))["ranked"][0]["listing"]["provider"] == "fixture"
    assert "provider,score" in render_csv(run)
    assert "Score breakdown" in render_detail(ranked)


def test_cli_overrides_config_without_changing_source() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["search", "--max-price", "300", "--quantity", "4", "--cpu", "Ryzen 7"]
    )
    config = apply_overrides(load_search_config("config/search.yaml"), args)
    assert config.search.price.max_per_unit == Decimal("300")
    assert config.search.quantity_required == 4
    assert config.search.cpu.preferred_models == ["Ryzen 7"]


def test_cli_search_with_no_enabled_providers_returns_valid_json(
    tmp_path: Path, capsys: object
) -> None:
    sites = tmp_path / "sites.yaml"
    sites.write_text("sites: {ebay: {enabled: false}}")
    exit_code = main(
        [
            "search",
            "--sites",
            str(sites),
            "--state",
            str(tmp_path / "state.db"),
            "--format",
            "json",
        ]
    )
    assert exit_code == 0
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert json.loads(output)["ranked"] == []


def test_cli_price_history_reports_persisted_observations(
    tmp_path: Path, capsys: object, good_listing: HardwareListing
) -> None:
    config = load_search_config("config/search.yaml")
    ranked = DealScorer(config.search, config.scoring, config.upgrade_costs).score(good_listing)
    state = tmp_path / "history.db"
    repository = SQLiteRepository(state)
    repository.save_run(SearchRun(ranked=[ranked], observed=[ranked], provider_results={}))
    exit_code = main(
        [
            "history",
            "fixture",
            "1",
            "--state",
            str(state),
            "--format",
            "json",
        ]
    )
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)  # type: ignore[attr-defined]
    assert output[0]["total_price"] == "250"
