//! 24時間移動雨量の計算（docs/calculation_method.md 4節）。

/// 直近window_hours時間（当該時刻を含む）の移動雨量合計。
/// 窓内に欠測(NaN)を含む場合、またはデータ先頭で窓が揃わない場合はNaNとする。
pub fn calculate_rolling_rainfall(values: &[f64], window_hours: usize) -> Vec<f64> {
    let n = values.len();
    let mut out = vec![f64::NAN; n];
    if window_hours == 0 {
        return out;
    }
    for i in 0..n {
        if i + 1 < window_hours {
            continue;
        }
        let start = i + 1 - window_hours;
        let window = &values[start..=i];
        if window.iter().any(|v| v.is_nan()) {
            continue;
        }
        out[i] = window.iter().sum();
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_simple_sum_of_24_hours() {
        let values = vec![1.0; 30];
        let r = calculate_rolling_rainfall(&values, 24);
        assert_eq!(r[23], 24.0);
        assert_eq!(r[29], 24.0);
    }

    #[test]
    fn nan_for_first_23_hours() {
        let values = vec![1.0; 30];
        let r = calculate_rolling_rainfall(&values, 24);
        for v in &r[0..23] {
            assert!(v.is_nan());
        }
    }
}
