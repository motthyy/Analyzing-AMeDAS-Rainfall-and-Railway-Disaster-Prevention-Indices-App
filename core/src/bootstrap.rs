//! ガンベル分布の確率雨量に対するブートストラップ信頼区間（docs/calculation_method.md 9.5節）。
//!
//! 注意: Python版はNumPyのPCG64乱数生成器を使うため、同一シードでもRust版
//! （`rand`クレートのデフォルトRNG）とは異なるリサンプル系列になり、個々の値は
//! 一致しない。したがって本モジュールの検証は「数値の完全一致」ではなく、
//! 「同一シードで再現可能」「分布として妥当」という統計的性質の確認に限定する
//! （tests/fixtures/golden/bootstrap.json 内のnoteを参照）。

use crate::gumbel::{fit_gumbel_mle, fit_gumbel_moments, return_period_value};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::collections::HashMap;

pub const SHORT_RECORD_WARNING_YEARS: i32 = 10;
pub const UNCERTAIN_RECORD_WARNING_YEARS: i32 = 20;
pub const EXTRAPOLATION_WARNING_FACTOR: f64 = 3.0;

pub struct BootstrapResult {
    pub lower: f64,
    pub upper: f64,
    pub median: f64,
}

pub fn bootstrap_return_period_ci(
    annual_maxima: &[f64],
    return_periods_years: &[f64],
    method: &str,
    n_iterations: u32,
    confidence_level: f64,
    random_seed: u64,
) -> HashMap<String, BootstrapResult> {
    let data: Vec<f64> = annual_maxima.iter().cloned().filter(|v| !v.is_nan()).collect();
    let n = data.len();

    let mut rng = StdRng::seed_from_u64(random_seed);
    let mut samples: HashMap<String, Vec<f64>> = return_periods_years.iter().map(|t| (t.to_string(), Vec::new())).collect();

    for _ in 0..n_iterations {
        let resample: Vec<f64> = (0..n).map(|_| data[rng.gen_range(0..n)]).collect();
        let params = if method == "mle" {
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| fit_gumbel_mle(&resample)))
        } else {
            std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| fit_gumbel_moments(&resample)))
        };
        let params = match params {
            Ok(p) if p.scale_beta.is_finite() && p.loc_mu.is_finite() => p,
            _ => continue,
        };
        for &t in return_periods_years {
            let v = return_period_value(params.loc_mu, params.scale_beta, t);
            if !v.is_nan() {
                samples.get_mut(&t.to_string()).unwrap().push(v);
            }
        }
    }

    let alpha = 1.0 - confidence_level;
    let lower_pct = alpha / 2.0;
    let upper_pct = 1.0 - alpha / 2.0;

    let mut results = HashMap::new();
    for (t_key, mut values) in samples {
        if values.is_empty() {
            results.insert(t_key, BootstrapResult { lower: f64::NAN, upper: f64::NAN, median: f64::NAN });
            continue;
        }
        values.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let percentile = |p: f64| -> f64 {
            let idx = (p * (values.len() as f64 - 1.0)).round() as usize;
            values[idx.min(values.len() - 1)]
        };
        results.insert(
            t_key,
            BootstrapResult {
                lower: percentile(lower_pct),
                upper: percentile(upper_pct),
                median: percentile(0.5),
            },
        );
    }
    results
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reproducible_with_same_seed() {
        let sample = [120.5, 98.2, 145.0, 110.3, 88.7, 200.1, 132.4, 99.9, 155.6, 121.0, 175.3, 105.8];
        let r1 = bootstrap_return_period_ci(&sample, &[10.0, 100.0], "mle", 200, 0.95, 123);
        let r2 = bootstrap_return_period_ci(&sample, &[10.0, 100.0], "mle", 200, 0.95, 123);
        assert_eq!(r1.get("10").unwrap().lower, r2.get("10").unwrap().lower);
    }
}
