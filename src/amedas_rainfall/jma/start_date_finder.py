"""時別降水量を取得できる最古の有効日時を探索する（4節）。

二分探索だけに依存せず、観測休止・長期欠測により「データの存在」が
年に対して単調にならない可能性を考慮した探索手順を実装する。

推奨探索手順（仕様書4節）に対応:
    1. 地点種別・メタデータから探索下限候補を取得
    2. 候補年の時別降水量が存在するか確認
    3. 10年単位→5年単位→1年単位で範囲を絞る
    4. 最古の有効年の前後を検証（安全マージンとして数年分を追加確認）
    5. その年のデータを取得
    6. 最初の有効な時別降水量日時を確定
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from dataclasses import dataclass, field
from typing import Protocol

from amedas_rainfall.jma.csv_parser import parse_jma_hourly_precipitation_csv

logger = logging.getLogger(__name__)

EARLIEST_POSSIBLE_YEAR = 1875
COARSE_STEPS = (10, 5, 1)
SAFETY_MARGIN_YEARS = 2


class SupportsCsvDownload(Protocol):
    def download_hourly_precipitation_csv(
        self,
        stid: str,
        start_year: int,
        start_month: int,
        start_day: int,
        end_year: int,
        end_month: int,
        end_day: int,
    ) -> bytes: ...


@dataclass
class StartDateSearchResult:
    earliest_valid_datetime: dt.datetime | None
    candidate_years_checked: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _probe_year_has_data(client: SupportsCsvDownload, station_code: str, year: int) -> bool:
    """指定年の1月1〜2日を取得し、品質情報コードが「非対象(0)」以外の行があるか確認する。"""
    try:
        raw = client.download_hourly_precipitation_csv(station_code, year, 1, 1, year, 1, 2)
        parsed = parse_jma_hourly_precipitation_csv(raw)
    except Exception:
        logger.exception("探索用プローブに失敗しました（station=%s, year=%s）", station_code, year)
        return False
    quality = parsed.frame["quality_code"]
    return bool((quality.notna() & (quality != "0")).any())


def find_earliest_valid_year(
    client: SupportsCsvDownload,
    station_code: str,
    candidate_year_hint: int,
    current_year: int,
    wait_seconds: float = 3.0,
) -> StartDateSearchResult:
    """時別降水量が最初に存在する年を探索する（非単調な欠測パターンを考慮）。"""
    checked: list[int] = []
    notes: list[str] = []

    def probe(year: int) -> bool:
        year = max(EARLIEST_POSSIBLE_YEAR, min(year, current_year))
        result = _probe_year_has_data(client, station_code, year)
        checked.append(year)
        time.sleep(wait_seconds)
        return result

    hint = max(EARLIEST_POSSIBLE_YEAR, min(candidate_year_hint, current_year))
    hint_has_data = probe(hint)

    if hint_has_data:
        # 候補年より前に遡って、データが存在しなくなる年を粗く探す
        last_found_year = hint
        boundary_no_data_year: int | None = None
        for step in COARSE_STEPS:
            year = last_found_year
            while True:
                prev_year = year - step
                if prev_year < EARLIEST_POSSIBLE_YEAR:
                    boundary_no_data_year = EARLIEST_POSSIBLE_YEAR - 1
                    break
                if probe(prev_year):
                    last_found_year = prev_year
                    year = prev_year
                    continue
                boundary_no_data_year = prev_year
                break
            if boundary_no_data_year == EARLIEST_POSSIBLE_YEAR - 1:
                break

        earliest_year = last_found_year
        # 安全マージン: 非単調な欠測を考慮し、境界のさらに前を追加確認する
        for extra in range(1, SAFETY_MARGIN_YEARS + 1):
            candidate = earliest_year - extra
            if candidate < EARLIEST_POSSIBLE_YEAR:
                break
            if probe(candidate):
                notes.append(
                    f"{earliest_year}年より前の{candidate}年にもデータが存在したため、探索範囲を広げました。"
                )
                earliest_year = candidate
    else:
        # 候補年よりデータが新しい場合は前方探索
        earliest_year = None
        year = hint
        for step in COARSE_STEPS:
            while earliest_year is None:
                next_year = year + step
                if next_year > current_year:
                    break
                if probe(next_year):
                    earliest_year = next_year
                    break
                year = next_year
        if earliest_year is None:
            return StartDateSearchResult(
                earliest_valid_datetime=None,
                candidate_years_checked=checked,
                notes=["候補年から現在年までデータが確認できませんでした。手動で開始年を指定してください。"],
            )

    earliest_valid_datetime = _find_first_valid_hour_in_year(client, station_code, earliest_year, wait_seconds)
    return StartDateSearchResult(
        earliest_valid_datetime=earliest_valid_datetime,
        candidate_years_checked=checked,
        notes=notes,
    )


def _find_first_valid_hour_in_year(
    client: SupportsCsvDownload, station_code: str, year: int, wait_seconds: float
) -> dt.datetime | None:
    raw = client.download_hourly_precipitation_csv(station_code, year, 1, 1, year, 12, 31)
    time.sleep(wait_seconds)
    parsed = parse_jma_hourly_precipitation_csv(raw)
    valid = parsed.frame[parsed.frame["quality_code"].notna() & (parsed.frame["quality_code"] != "0")]
    if valid.empty:
        return None
    return valid.index.min().to_pydatetime()


def default_start_year_hint(station_type_is_amedas: bool) -> int:
    """地点種別からの探索下限候補（一般的な観測開始年の目安）。"""
    # AMeDASは1974年11月から順次運用開始、気象官署はそれ以前から観測している場合が多い。
    return 1974 if station_type_is_amedas else 1875
