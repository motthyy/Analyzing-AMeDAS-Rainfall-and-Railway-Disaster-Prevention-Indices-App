//! 実効雨量（半減期減衰型指数平滑雨量）の計算（docs/calculation_method.md 5節）。
//!
//! 半減期H[時間]に対する1時間あたりの残存率: a_H = 0.5^(1/H)
//! 漸化式: E_H(t) = r_t + a_H * E_H(t-1)

pub struct EffectiveRainfallResult {
    pub values: Vec<f64>,
    pub state_reset_due_to_gap: Vec<bool>,
    pub warmup_flag: Vec<bool>,
}

pub fn half_life_to_decay_rate(half_life_hours: f64) -> f64 {
    0.5_f64.powf(1.0 / half_life_hours)
}

pub fn calculate_effective_rainfall(values: &[f64], half_life_hours: f64) -> EffectiveRainfallResult {
    let decay = half_life_to_decay_rate(half_life_hours);
    let n = values.len();
    let mut out = vec![f64::NAN; n];
    let mut reset_due_to_gap = vec![false; n];
    let mut warmup = vec![false; n];

    let mut prev = 0.0_f64;
    let mut pending_reset = true;
    for i in 0..n {
        let val = values[i];
        if val.is_nan() {
            pending_reset = true;
            continue;
        }
        if pending_reset {
            prev = 0.0;
            warmup[i] = true;
            reset_due_to_gap[i] = true;
            pending_reset = false;
        }
        let cur = val + decay * prev;
        out[i] = cur;
        prev = cur;
    }

    EffectiveRainfallResult {
        values: out,
        state_reset_due_to_gap: reset_due_to_gap,
        warmup_flag: warmup,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn value_is_half_after_one_half_life() {
        let mut values = vec![10.0];
        values.extend(vec![0.0; 6]);
        let r = calculate_effective_rainfall(&values, 6.0);
        assert!((r.values[6] - 5.0).abs() < 1e-9);
    }
}
