//! 時別降水量データの正規化処理（docs/calculation_method.md 1.2節）。

pub const NO_RAIN_THRESHOLD_MM: f64 = 0.3;

/// 0.3mm/h以下を「無降雨」とみなす閾値処理を行い、計算用時雨量を返す。
/// 欠測(NaN)はこの変換の対象外とし、NaNのまま維持する（0へは変換しない）。
pub fn apply_no_rain_threshold(raw_mm: &[f64], threshold_mm: f64) -> Vec<f64> {
    raw_mm
        .iter()
        .map(|&v| {
            if v.is_nan() || v > threshold_mm {
                v
            } else {
                0.0
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn threshold_0_3_is_no_rain_0_4_is_rain() {
        let raw = [0.0, 0.1, 0.2, 0.3, 0.4];
        let used = apply_no_rain_threshold(&raw, NO_RAIN_THRESHOLD_MM);
        assert_eq!(used, vec![0.0, 0.0, 0.0, 0.0, 0.4]);
    }

    #[test]
    fn missing_values_are_not_zeroed() {
        let raw = [0.5, f64::NAN, 1.0];
        let used = apply_no_rain_threshold(&raw, NO_RAIN_THRESHOLD_MM);
        assert!(used[1].is_nan());
    }
}
