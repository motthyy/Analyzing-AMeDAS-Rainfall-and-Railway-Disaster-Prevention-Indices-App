//! ガンベル分布による確率雨量の推定（docs/calculation_method.md 9節）。
//!
//! 最尤法(MLE)はscipy `gumbel_r.fit` のような汎用最適化ルーチンではなく、
//! Gumbel分布のMLE方程式（プロファイル尤度によるbetaの不動点方程式）を
//! 直接反復法で解く。数学的には同一の最尤推定値に収束するが、収束判定・
//! 浮動小数点誤差の都合上、scipy版とは1e-6程度の相対誤差が生じ得る
//! （数値一致ではなく統計的等価性の確認とする）。

pub const EULER_MASCHERONI: f64 = 0.5772156649015329;

pub const STANDARD_RETURN_PERIODS: &[f64] = &[
    1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0,
    18.0, 19.0, 20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0, 50.0, 100.0,
];

pub struct GumbelParameters {
    pub loc_mu: f64,
    pub scale_beta: f64,
}

pub struct GoodnessOfFit {
    pub aic: Option<f64>,
    pub ks_statistic: Option<f64>,
    pub rmse: Option<f64>,
    pub correlation: Option<f64>,
}

fn clean(data: &[f64]) -> Vec<f64> {
    data.iter().cloned().filter(|v| !v.is_nan()).collect()
}

pub fn fit_gumbel_moments(annual_maxima: &[f64]) -> GumbelParameters {
    let data = clean(annual_maxima);
    let n = data.len() as f64;
    let mean = data.iter().sum::<f64>() / n;
    let variance = data.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n - 1.0);
    let std = variance.sqrt();
    let beta = 6.0_f64.sqrt() * std / std::f64::consts::PI;
    let mu = mean - EULER_MASCHERONI * beta;
    GumbelParameters { loc_mu: mu, scale_beta: beta }
}

/// Gumbel分布のMLE方程式を不動点反復で解く。
/// beta = mean - Σ x_i exp(-x_i/beta) / Σ exp(-x_i/beta)
/// mu   = -beta * ln( mean(exp(-x_i/beta)) )
pub fn fit_gumbel_mle(annual_maxima: &[f64]) -> GumbelParameters {
    let data = clean(annual_maxima);
    let n = data.len() as f64;
    let mean = data.iter().sum::<f64>() / n;

    let moments = fit_gumbel_moments(&data);
    let mut beta = moments.scale_beta.max(1e-9);

    for _ in 0..500 {
        let exp_terms: Vec<f64> = data.iter().map(|&x| (-x / beta).exp()).collect();
        let sum_exp: f64 = exp_terms.iter().sum();
        let weighted: f64 = data.iter().zip(&exp_terms).map(|(&x, &e)| x * e).sum();
        let new_beta = mean - weighted / sum_exp;
        let diff = (new_beta - beta).abs();
        beta = new_beta;
        if diff < 1e-14 {
            break;
        }
    }

    let exp_terms_final: Vec<f64> = data.iter().map(|&x| (-x / beta).exp()).collect();
    let sum_exp_final: f64 = exp_terms_final.iter().sum();
    let mu = -beta * (sum_exp_final / n).ln();

    GumbelParameters { loc_mu: mu, scale_beta: beta }
}

/// 確率年Tに対する確率雨量 x_T を計算する。T<=1年は算出不可としてNaNを返す。
pub fn return_period_value(mu: f64, beta: f64, return_period_years: f64) -> f64 {
    if return_period_years <= 1.0 {
        return f64::NAN;
    }
    mu - beta * (-(1.0 - 1.0 / return_period_years).ln()).ln()
}

pub fn return_period_values(mu: f64, beta: f64, return_periods_years: &[f64]) -> Vec<f64> {
    return_periods_years
        .iter()
        .map(|&t| return_period_value(mu, beta, t))
        .collect()
}

/// プロッティングポジション公式による非超過確率F_mを、昇順順位m=1..nに対して返す。
pub fn plotting_positions(n: usize, method: &str) -> Vec<f64> {
    let (a, b) = match method {
        "gringorten" => (0.44, 0.12),
        "weibull" => (0.0, 1.0),
        "cunnane" => (0.4, 0.2),
        _ => panic!("未知のプロッティングポジション法: {method}"),
    };
    (1..=n).map(|m| (m as f64 - a) / (n as f64 + b)).collect()
}

pub fn empirical_return_periods(n: usize, method: &str) -> Vec<f64> {
    plotting_positions(n, method).iter().map(|f_m| 1.0 / (1.0 - f_m)).collect()
}

fn gumbel_logpdf(x: f64, mu: f64, beta: f64) -> f64 {
    let z = (x - mu) / beta;
    -z - (-z).exp() - beta.ln()
}

fn gumbel_cdf(x: f64, mu: f64, beta: f64) -> f64 {
    (-(-(x - mu) / beta).exp()).exp()
}

/// Kolmogorov-Smirnov統計量（完全指定分布に対する両側検定）。
fn ks_statistic(sorted_data: &[f64], mu: f64, beta: f64) -> f64 {
    let n = sorted_data.len() as f64;
    let mut d_max = 0.0_f64;
    for (i, &x) in sorted_data.iter().enumerate() {
        let f = gumbel_cdf(x, mu, beta);
        let d1 = (f - (i as f64) / n).abs();
        let d2 = (f - (i as f64 + 1.0) / n).abs();
        d_max = d_max.max(d1).max(d2);
    }
    d_max
}

pub fn goodness_of_fit(annual_maxima: &[f64], params: &GumbelParameters, plotting_position: &str) -> GoodnessOfFit {
    let mut data = clean(annual_maxima);
    data.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = data.len();
    if n < 2 {
        return GoodnessOfFit { aic: None, ks_statistic: None, rmse: None, correlation: None };
    }

    let loglik: f64 = data.iter().map(|&x| gumbel_logpdf(x, params.loc_mu, params.scale_beta)).sum();
    let aic = 2.0 * 2.0 - 2.0 * loglik;

    let ks = ks_statistic(&data, params.loc_mu, params.scale_beta);

    let t_m = empirical_return_periods(n, plotting_position);
    let predicted: Vec<f64> = t_m.iter().map(|&t| return_period_value(params.loc_mu, params.scale_beta, t)).collect();

    let pairs: Vec<(f64, f64)> = data.iter().zip(predicted.iter()).filter(|(_, p)| !p.is_nan()).map(|(&d, &p)| (d, p)).collect();
    let (rmse, correlation) = if pairs.len() >= 2 {
        let mse = pairs.iter().map(|(d, p)| (d - p).powi(2)).sum::<f64>() / pairs.len() as f64;
        let mean_d = pairs.iter().map(|(d, _)| d).sum::<f64>() / pairs.len() as f64;
        let mean_p = pairs.iter().map(|(_, p)| p).sum::<f64>() / pairs.len() as f64;
        let cov: f64 = pairs.iter().map(|(d, p)| (d - mean_d) * (p - mean_p)).sum();
        let std_d = pairs.iter().map(|(d, _)| (d - mean_d).powi(2)).sum::<f64>().sqrt();
        let std_p = pairs.iter().map(|(_, p)| (p - mean_p).powi(2)).sum::<f64>().sqrt();
        (Some(mse.sqrt()), Some(cov / (std_d * std_p)))
    } else {
        (None, None)
    };

    GoodnessOfFit { aic: Some(aic), ks_statistic: Some(ks), rmse, correlation }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn return_period_1_year_is_nan() {
        assert!(return_period_value(100.0, 20.0, 1.0).is_nan());
    }

    #[test]
    fn return_period_value_is_monotonically_increasing() {
        let values: Vec<f64> = [2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0]
            .iter()
            .map(|&t| return_period_value(100.0, 20.0, t))
            .collect();
        for w in values.windows(2) {
            assert!(w[1] > w[0]);
        }
    }
}
