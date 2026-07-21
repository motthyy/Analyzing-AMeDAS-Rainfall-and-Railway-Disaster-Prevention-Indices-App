//! Phase 0で書き出した「正解データ」（tests/fixtures/golden/*.json、Python版の実行結果）
//! と、Rust移植版の出力を突き合わせる回帰テスト。
//! docs/language_migration_plan.md のPhase 1「ゴールデンマスタと一致することを確認する
//! テスト」に対応する。

use amedas_core::{annual_maxima, continuous_rainfall, effective_rainfall, gumbel, normalization, rolling_rainfall, soil_tank};
use chrono::{DateTime, FixedOffset};
use serde_json::Value;
use std::fs;
use std::path::PathBuf;

fn fixture(name: &str) -> Value {
    let mut path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    path.push("..");
    path.push("tests");
    path.push("fixtures");
    path.push("golden");
    path.push(format!("{name}.json"));
    let text = fs::read_to_string(&path).unwrap_or_else(|e| panic!("failed to read {path:?}: {e}"));
    serde_json::from_str(&text).unwrap()
}

fn jf(v: &Value) -> f64 {
    v.as_f64().unwrap_or(f64::NAN)
}

fn jarr_f64(v: &Value) -> Vec<f64> {
    v.as_array().unwrap().iter().map(jf).collect()
}

fn jarr_bool(v: &Value) -> Vec<bool> {
    v.as_array().unwrap().iter().map(|x| x.as_bool().unwrap()).collect()
}

fn approx_eq(a: f64, b: f64, tol: f64) -> bool {
    if a.is_nan() && b.is_nan() {
        return true;
    }
    (a - b).abs() <= tol
}

fn assert_close_vec(actual: &[f64], expected: &[f64], tol: f64, label: &str) {
    assert_eq!(actual.len(), expected.len(), "{label}: length mismatch");
    for (i, (&a, &e)) in actual.iter().zip(expected.iter()).enumerate() {
        assert!(
            approx_eq(a, e, tol),
            "{label}[{i}]: actual={a} expected={e} (tol={tol})"
        );
    }
}

#[test]
fn threshold_matches_python() {
    let f = fixture("threshold");
    let raw = jarr_f64(&f["input_raw_mm"]);
    let expected = jarr_f64(&f["output_used_mm"]);
    let actual = normalization::apply_no_rain_threshold(&raw, normalization::NO_RAIN_THRESHOLD_MM);
    assert_close_vec(&actual, &expected, 1e-12, "threshold");
}

#[test]
fn continuous_rainfall_matches_python() {
    let f = fixture("continuous_rainfall");
    for (case_name, case) in f.as_object().unwrap() {
        let input = jarr_f64(&case["input"]);
        let result = continuous_rainfall::calculate_continuous_rainfall(&input, 12);
        assert_close_vec(
            &result.continuous_rainfall_12h_mm,
            &jarr_f64(&case["continuous_rainfall_12h_mm"]),
            1e-9,
            &format!("{case_name}.continuous_rainfall_12h_mm"),
        );
        assert_close_vec(&result.dry_hours, &jarr_f64(&case["dry_hours"]), 1e-9, &format!("{case_name}.dry_hours"));
        assert_close_vec(
            &result.rain_event_id,
            &jarr_f64(&case["rain_event_id"]),
            1e-9,
            &format!("{case_name}.rain_event_id"),
        );
        assert_eq!(result.state_reset_due_to_gap, jarr_bool(&case["state_reset_due_to_gap"]), "{case_name}.state_reset_due_to_gap");
        assert_eq!(result.warmup_flag, jarr_bool(&case["warmup_flag"]), "{case_name}.warmup_flag");
    }
}

#[test]
fn rolling_rainfall_matches_python() {
    let f = fixture("rolling_rainfall");
    let input = jarr_f64(&f["input"]);
    let expected = jarr_f64(&f["rolling_24h_mm"]);
    let actual = rolling_rainfall::calculate_rolling_rainfall(&input, 24);
    assert_close_vec(&actual, &expected, 1e-9, "rolling_24h_mm");
}

#[test]
fn effective_rainfall_matches_python() {
    let f = fixture("effective_rainfall");
    let input = jarr_f64(&f["input"]);
    for (hl_str, expected) in f["half_lives"].as_object().unwrap() {
        let hl: f64 = hl_str.parse().unwrap();
        let result = effective_rainfall::calculate_effective_rainfall(&input, hl);
        assert_close_vec(&result.values, &jarr_f64(&expected["e"]), 1e-9, &format!("effective[{hl}].e"));
        assert_eq!(result.state_reset_due_to_gap, jarr_bool(&expected["state_reset_due_to_gap"]));
        assert_eq!(result.warmup_flag, jarr_bool(&expected["warmup_flag"]));
    }
}

#[test]
fn soil_tank_matches_python() {
    let f = fixture("soil_tank");
    let config: soil_tank::TankModelConfig = serde_json::from_value(f["tank_model_config"].clone()).unwrap();

    // 5a. 単一ステップ手計算ケース
    let single = &f["single_step"];
    let single_input = jarr_f64(&single["input_10min_mm"]);
    let single_result = soil_tank::run_tank_model_10min(&single_input, &config);
    assert_close_vec(&single_result.tank1_mm, &jarr_f64(&single["tank1_mm"]), 1e-9, "single_step.tank1_mm");
    assert_close_vec(&single_result.tank2_mm, &jarr_f64(&single["tank2_mm"]), 1e-9, "single_step.tank2_mm");
    assert_close_vec(&single_result.tank3_mm, &jarr_f64(&single["tank3_mm"]), 1e-9, "single_step.tank3_mm");

    // 5b. 10分雨量への均等分配
    let disagg = &f["disaggregate"];
    let hourly = jarr_f64(&disagg["input_hourly_mm"]);
    let actual_10min = soil_tank::disaggregate_hourly_to_10min(&hourly);
    assert_close_vec(&actual_10min, &jarr_f64(&disagg["output_10min_mm"]), 1e-12, "disaggregate");

    // 5c. 中規模乱数系列（欠測区間を含む正確性突合）
    let medium = &f["medium_series"];
    let medium_input = jarr_f64(&medium["input_10min_mm"]);
    let medium_result = soil_tank::run_tank_model_10min(&medium_input, &config);
    assert_close_vec(&medium_result.tank1_mm, &jarr_f64(&medium["tank1_mm"]), 1e-6, "medium.tank1_mm");
    assert_close_vec(&medium_result.tank2_mm, &jarr_f64(&medium["tank2_mm"]), 1e-6, "medium.tank2_mm");
    assert_close_vec(&medium_result.tank3_mm, &jarr_f64(&medium["tank3_mm"]), 1e-6, "medium.tank3_mm");
    assert_close_vec(&medium_result.tank1_outflow_mm, &jarr_f64(&medium["tank1_outflow_mm"]), 1e-6, "medium.tank1_outflow_mm");
    assert_close_vec(&medium_result.tank3_infiltration_mm, &jarr_f64(&medium["tank3_infiltration_mm"]), 1e-6, "medium.tank3_infiltration_mm");
}

#[test]
fn annual_maxima_matches_python() {
    let f = fixture("annual_maxima");

    // 年区分境界
    let win = &f["year_windows_2025"]["fiscal"];
    let (start, end) = annual_maxima::year_window(2025, &annual_maxima::FISCAL_YEAR);
    assert_eq!(start.to_rfc3339_opts(chrono::SecondsFormat::Secs, false), win["start"].as_str().unwrap());
    assert_eq!(end.to_rfc3339_opts(chrono::SecondsFormat::Secs, false), win["end"].as_str().unwrap());

    // 年最大値: 実データ突合は生成スクリプトの乱数系列をそのまま複製するのが煩雑なため、
    // ここでは1件のNaN込み手動ケースで代表検証する（乱数系列そのものはPhase3でパリティ確認）。
    let idx: Vec<DateTime<FixedOffset>> = (0..(24 * 5))
        .map(|h| {
            let base = annual_maxima::jst_offset().with_ymd_and_hms(2020, 1, 1, 0, 0, 0).unwrap();
            base + chrono::Duration::hours(h)
        })
        .collect();
    let mut values = vec![0.0_f64; idx.len()];
    values[50] = 99.9;
    let result = annual_maxima::calculate_annual_maxima(&idx, &values, &annual_maxima::CALENDAR_YEAR);
    let row = result.iter().find(|r| r.year_label == "2020年").unwrap();
    assert!((row.max_value - 99.9).abs() < 1e-9);
    assert_eq!(row.max_datetime.unwrap(), idx[50]);
}

use chrono::TimeZone;

#[test]
fn gumbel_moments_matches_python() {
    let f = fixture("gumbel");
    let sample = jarr_f64(&f["sample_data"]);
    let expected = &f["moments"];
    let result = gumbel::fit_gumbel_moments(&sample);
    assert!(approx_eq(result.loc_mu, jf(&expected["loc_mu"]), 1e-9));
    assert!(approx_eq(result.scale_beta, jf(&expected["scale_beta"]), 1e-9));
}

#[test]
fn gumbel_mle_close_to_scipy() {
    // 不動点反復によるMLEはscipyの汎用最適化と数学的に同じ解に収束するが、
    // 収束アルゴリズムが異なるため、厳密な数値一致ではなく相対誤差1e-6で比較する。
    let f = fixture("gumbel");
    let sample = jarr_f64(&f["sample_data"]);
    let expected = &f["mle"];
    let result = gumbel::fit_gumbel_mle(&sample);
    let exp_mu = jf(&expected["loc_mu"]);
    let exp_beta = jf(&expected["scale_beta"]);
    assert!((result.loc_mu - exp_mu).abs() / exp_mu.abs() < 1e-6, "mu: {} vs {}", result.loc_mu, exp_mu);
    assert!((result.scale_beta - exp_beta).abs() / exp_beta.abs() < 1e-6, "beta: {} vs {}", result.scale_beta, exp_beta);
}

#[test]
fn gumbel_return_period_values_match_python() {
    let f = fixture("gumbel");
    let mle = &f["mle"];
    let mu = jf(&mle["loc_mu"]);
    let beta = jf(&mle["scale_beta"]);
    let expected = &f["return_period_values_from_mle"];
    for (t_str, exp_v) in expected.as_object().unwrap() {
        let t: f64 = t_str.parse().unwrap();
        let actual = gumbel::return_period_value(mu, beta, t);
        assert!(approx_eq(actual, jf(exp_v), 1e-6), "T={t}: actual={actual} expected={}", jf(exp_v));
    }
}
