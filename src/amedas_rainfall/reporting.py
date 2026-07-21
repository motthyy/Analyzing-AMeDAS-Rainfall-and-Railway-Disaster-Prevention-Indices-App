"""時別データ・年最大値・確率雨量のCSV/Parquet/Excel出力（15節）。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd

EXCEL_MAX_ROWS = 1_048_576
EXCEL_SAFE_ROW_LIMIT = EXCEL_MAX_ROWS - 10

ProgressCallback = Callable[[float, str], None]


def _report(callback: ProgressCallback | None, fraction: float, message: str) -> None:
    if callback is not None:
        callback(fraction, message)


def _strip_tz(value):
    if hasattr(value, "tzinfo") and value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


def _strip_timezone_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Excel(xlsxwriter/openpyxl)はタイムゾーン付き日時を書き込めないため、
    出力直前にタイムゾーンを除去したコピーを返す（値そのもの＝JSTのローカル時刻は変えない）。
    """
    df = df.copy()
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    for col in df.columns:
        if isinstance(df[col].dtype, pd.DatetimeTZDtype):
            df[col] = df[col].dt.tz_localize(None)
        elif df[col].dtype == object:
            df[col] = df[col].map(_strip_tz)
    return df


def export_hourly_data(
    df: pd.DataFrame,
    output_dir_parquet: Path,
    output_dir_csv: Path,
    output_dir_excel: Path,
    basename: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Path | None]:
    """時別データをParquet/CSV/Excelへ出力する。行数がExcel上限を超える場合はExcelを省略する。"""
    output_dir_parquet.mkdir(parents=True, exist_ok=True)
    output_dir_csv.mkdir(parents=True, exist_ok=True)
    output_dir_excel.mkdir(parents=True, exist_ok=True)

    parquet_path = output_dir_parquet / f"{basename}.parquet"
    csv_path = output_dir_csv / f"{basename}.csv"

    _report(progress_callback, 0.0, "Parquetファイルを書き出しています")
    df.to_parquet(parquet_path)

    _report(progress_callback, 0.4, "CSVファイルを書き出しています")
    df.to_csv(csv_path, encoding="utf-8-sig")

    excel_path: Path | None = output_dir_excel / f"{basename}.xlsx"
    if len(df) > EXCEL_SAFE_ROW_LIMIT:
        excel_path = None  # Excel上限超過のため出力しない（CSV/Parquetを案内）
    else:
        _report(progress_callback, 0.7, "Excelファイルを書き出しています")
        with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
            _strip_timezone_for_excel(df).to_excel(writer, sheet_name="時別データ")

    _report(progress_callback, 1.0, "出力が完了しました")
    return {"parquet": parquet_path, "csv": csv_path, "excel": excel_path}


def export_annual_maxima(
    maxima_by_boundary: dict[str, pd.DataFrame],
    output_dir_parquet: Path,
    output_dir_csv: Path,
    output_dir_excel: Path,
    basename: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Path]:
    output_dir_parquet.mkdir(parents=True, exist_ok=True)
    output_dir_csv.mkdir(parents=True, exist_ok=True)
    output_dir_excel.mkdir(parents=True, exist_ok=True)

    _report(progress_callback, 0.0, "年最大値をまとめています")
    combined = pd.concat(
        [df.assign(year_boundary_type=key) for key, df in maxima_by_boundary.items()],
        ignore_index=True,
    )
    parquet_path = output_dir_parquet / f"{basename}.parquet"
    csv_path = output_dir_csv / f"{basename}.csv"
    excel_path = output_dir_excel / f"{basename}.xlsx"

    _report(progress_callback, 0.2, "Parquetファイルを書き出しています")
    combined.to_parquet(parquet_path)

    _report(progress_callback, 0.4, "CSVファイルを書き出しています")
    combined.to_csv(csv_path, index=False, encoding="utf-8-sig")

    _report(progress_callback, 0.6, "Excelファイルを書き出しています")
    sheet_name_map = {"calendar": "年最大値_暦年", "fiscal": "年最大値_年度", "june_start": "年最大値_6月始まり"}
    with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
        for key, df in maxima_by_boundary.items():
            _strip_timezone_for_excel(df).to_excel(writer, sheet_name=sheet_name_map.get(key, key)[:31], index=False)

    _report(progress_callback, 1.0, "出力が完了しました")
    return {"parquet": parquet_path, "csv": csv_path, "excel": excel_path}


def export_probability_results(
    probability_table: pd.DataFrame,
    parameters_table: pd.DataFrame,
    output_dir_csv: Path,
    output_dir_excel: Path,
    basename: str,
) -> dict[str, Path]:
    output_dir_csv.mkdir(parents=True, exist_ok=True)
    output_dir_excel.mkdir(parents=True, exist_ok=True)

    csv_path = output_dir_csv / f"{basename}.csv"
    json_path = output_dir_csv / f"{basename}.json"
    excel_path = output_dir_excel / f"{basename}.xlsx"

    probability_table.to_csv(csv_path, index=False, encoding="utf-8-sig")
    probability_table.to_json(json_path, orient="records", force_ascii=False, indent=2)

    with pd.ExcelWriter(excel_path, engine="xlsxwriter") as writer:
        _strip_timezone_for_excel(probability_table).to_excel(writer, sheet_name="確率雨量", index=False)
        _strip_timezone_for_excel(parameters_table).to_excel(writer, sheet_name="ガンベル推定値", index=False)

    return {"csv": csv_path, "json": json_path, "excel": excel_path}


def build_full_excel_workbook(
    output_path: Path,
    station_info: pd.DataFrame,
    hourly_df: pd.DataFrame | None,
    annual_maxima_by_boundary: dict[str, pd.DataFrame],
    probability_table: pd.DataFrame,
    gumbel_parameters_table: pd.DataFrame,
    excluded_years_table: pd.DataFrame,
    missing_data_table: pd.DataFrame,
    calculation_conditions: pd.DataFrame,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """15節の全シート構成を持つExcelブックを1ファイルにまとめて出力する。

    時別データの行数がExcel上限を超える場合は、当該シートを省略し、
    かわりに案内メッセージを記載する。
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet_name_map = {"calendar": "年最大値_暦年", "fiscal": "年最大値_年度", "june_start": "年最大値_6月始まり"}
    # シート書き込みの合計数（進捗率の分母）: 地点情報+時別データ+年最大値3種+確率雨量+
    # ガンベル推定値+除外年+欠測一覧+計算条件
    total_steps = 4 + len(annual_maxima_by_boundary)
    step = 0

    def _step(message: str) -> None:
        nonlocal step
        _report(progress_callback, step / total_steps, message)
        step += 1

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        _step("地点情報シートを書き出しています")
        _strip_timezone_for_excel(station_info).to_excel(writer, sheet_name="地点情報", index=False)

        _step("時別データシートを書き出しています")
        if hourly_df is not None and len(hourly_df) <= EXCEL_SAFE_ROW_LIMIT:
            _strip_timezone_for_excel(hourly_df).to_excel(writer, sheet_name="時別データ")
        else:
            note_df = pd.DataFrame(
                {
                    "注記": [
                        "時別データの行数がExcelの上限に近いため、このシートには格納していません。",
                        "output/csv または data/normalized のParquet/CSVファイルを参照してください。",
                    ]
                }
            )
            note_df.to_excel(writer, sheet_name="時別データ", index=False)

        for key, df in annual_maxima_by_boundary.items():
            _step(f"{sheet_name_map.get(key, key)}シートを書き出しています")
            _strip_timezone_for_excel(df).to_excel(
                writer, sheet_name=sheet_name_map.get(key, key)[:31], index=False
            )

        _step("確率雨量・ガンベル推定値・除外年・欠測一覧・計算条件シートを書き出しています")
        _strip_timezone_for_excel(probability_table).to_excel(writer, sheet_name="確率雨量", index=False)
        _strip_timezone_for_excel(gumbel_parameters_table).to_excel(
            writer, sheet_name="ガンベル推定値", index=False
        )
        _strip_timezone_for_excel(excluded_years_table).to_excel(writer, sheet_name="除外年", index=False)
        _strip_timezone_for_excel(missing_data_table).to_excel(writer, sheet_name="欠測一覧", index=False)
        _strip_timezone_for_excel(calculation_conditions).to_excel(
            writer, sheet_name="計算条件", index=False
        )

    _report(progress_callback, 1.0, "出力が完了しました")
    return output_path


def save_json(data: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
