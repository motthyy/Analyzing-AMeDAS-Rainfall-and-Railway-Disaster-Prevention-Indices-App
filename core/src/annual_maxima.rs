//! 3種類の年区切りによる年最大値・データ完全性の計算（docs/calculation_method.md 8節）。
//!
//! Asia/Tokyoはサマータイムを持たないため、固定UTC+9オフセットとして扱う。

use chrono::{DateTime, FixedOffset, TimeZone};

pub struct YearBoundary {
    pub key: &'static str,
    pub start_month: u32,
    pub start_day: u32,
}

pub const CALENDAR_YEAR: YearBoundary = YearBoundary { key: "calendar", start_month: 1, start_day: 1 };
pub const FISCAL_YEAR: YearBoundary = YearBoundary { key: "fiscal", start_month: 4, start_day: 1 };
pub const JUNE_START_YEAR: YearBoundary = YearBoundary { key: "june_start", start_month: 6, start_day: 1 };

pub fn jst_offset() -> FixedOffset {
    FixedOffset::east_opt(9 * 3600).unwrap()
}

pub fn year_window(start_year: i32, boundary: &YearBoundary) -> (DateTime<FixedOffset>, DateTime<FixedOffset>) {
    let tz = jst_offset();
    let start = tz
        .with_ymd_and_hms(start_year, boundary.start_month, boundary.start_day, 0, 0, 0)
        .unwrap();
    let end = tz
        .with_ymd_and_hms(start_year + 1, boundary.start_month, boundary.start_day, 0, 0, 0)
        .unwrap();
    (start, end)
}

pub fn year_label(start_year: i32, boundary: &YearBoundary) -> String {
    match boundary.key {
        "calendar" => format!("{start_year}年"),
        "fiscal" => format!("{start_year}年度"),
        "june_start" => format!("{start_year}年6月始まり"),
        _ => format!("{start_year}年"),
    }
}

fn start_year_for_timestamp(ts: &DateTime<FixedOffset>, boundary: &YearBoundary) -> i32 {
    use chrono::Datelike;
    let md = (ts.month(), ts.day());
    if md >= (boundary.start_month, boundary.start_day) {
        ts.year()
    } else {
        ts.year() - 1
    }
}

pub struct AnnualMaximum {
    pub year_label: String,
    pub start_year: i32,
    pub max_value: f64,
    pub max_datetime: Option<DateTime<FixedOffset>>,
}

/// 指定した年区分での年最大値とその発生日時を計算する。
/// 同値の場合は最初に出現した時刻を採用する（pandas `idxmax` と同じ挙動）。
pub fn calculate_annual_maxima(
    index: &[DateTime<FixedOffset>],
    values: &[f64],
    boundary: &YearBoundary,
) -> Vec<AnnualMaximum> {
    use std::collections::BTreeMap;
    let mut groups: BTreeMap<i32, Vec<(DateTime<FixedOffset>, f64)>> = BTreeMap::new();
    for (ts, &v) in index.iter().zip(values.iter()) {
        let sy = start_year_for_timestamp(ts, boundary);
        groups.entry(sy).or_default().push((*ts, v));
    }
    groups
        .into_iter()
        .map(|(sy, entries)| {
            let mut max_v = f64::NAN;
            let mut max_dt: Option<DateTime<FixedOffset>> = None;
            for (ts, v) in entries {
                if v.is_nan() {
                    continue;
                }
                if max_dt.is_none() || v > max_v {
                    max_v = v;
                    max_dt = Some(ts);
                }
            }
            AnnualMaximum {
                year_label: year_label(sy, boundary),
                start_year: sy,
                max_value: max_v,
                max_datetime: max_dt,
            }
        })
        .collect()
}

pub struct AnnualCompleteness {
    pub year_label: String,
    pub expected_hours: i64,
    pub valid_hours: i64,
    pub missing_hours: i64,
    pub completeness_percent: f64,
    pub has_state_reset: bool,
    pub is_eligible_default: bool,
    pub exclusion_reasons: Vec<String>,
}

/// 年区分ごとのデータ完全性を評価し、既定の採否判定を付ける。
#[allow(clippy::too_many_arguments)]
pub fn calculate_annual_completeness(
    index: &[DateTime<FixedOffset>],
    valid_mask: &[bool],
    boundary: &YearBoundary,
    state_reset_mask: Option<&[bool]>,
    completeness_threshold_percent: f64,
    data_start: DateTime<FixedOffset>,
    data_end: DateTime<FixedOffset>,
    now: DateTime<FixedOffset>,
) -> Vec<AnnualCompleteness> {
    if index.is_empty() {
        return vec![];
    }
    let start_year_min = start_year_for_timestamp(&data_start, boundary);
    let start_year_max = start_year_for_timestamp(&data_end, boundary) + 1;

    let mut results = Vec::new();
    for start_year in start_year_min..=start_year_max {
        let (win_start, win_end) = year_window(start_year, boundary);
        let mut expected_hours: i64 = 0;
        let mut valid_hours: i64 = 0;
        let mut has_reset = false;
        for (i, ts) in index.iter().enumerate() {
            if *ts >= win_start && *ts < win_end {
                expected_hours += 1;
                if valid_mask[i] {
                    valid_hours += 1;
                }
                if let Some(sr) = state_reset_mask {
                    if sr[i] {
                        has_reset = true;
                    }
                }
            }
        }
        if expected_hours == 0 {
            continue;
        }
        let missing_hours = expected_hours - valid_hours;
        let completeness = 100.0 * valid_hours as f64 / expected_hours as f64;

        let mut reasons = Vec::new();
        let is_incomplete_start = win_start < data_start && data_start <= win_end;
        let is_ongoing_latest = win_end > now;
        if is_incomplete_start {
            reasons.push("観測開始を含む不完全年".to_string());
        }
        if is_ongoing_latest {
            reasons.push("実行時点で終了していない最新年区分".to_string());
        }
        if completeness < completeness_threshold_percent {
            reasons.push(format!("データ完全率が{completeness_threshold_percent}%未満"));
        }
        if has_reset {
            reasons.push("大きな欠測により状態量が再初期化された区間を含む".to_string());
        }
        let is_eligible = reasons.is_empty();

        results.push(AnnualCompleteness {
            year_label: year_label(start_year, boundary),
            expected_hours,
            valid_hours,
            missing_hours,
            completeness_percent: completeness,
            has_state_reset: has_reset,
            is_eligible_default: is_eligible,
            exclusion_reasons: reasons,
        });
    }
    results
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fiscal_year_window_boundaries() {
        let (start, end) = year_window(2025, &FISCAL_YEAR);
        use chrono::Datelike;
        assert_eq!((start.month(), start.day(), start.year()), (4, 1, 2025));
        assert_eq!((end.month(), end.day(), end.year()), (4, 1, 2026));
    }

    #[test]
    fn year_labels_are_formatted_correctly() {
        assert_eq!(year_label(2025, &CALENDAR_YEAR), "2025年");
        assert_eq!(year_label(2025, &FISCAL_YEAR), "2025年度");
        assert_eq!(year_label(2025, &JUNE_START_YEAR), "2025年6月始まり");
    }
}
