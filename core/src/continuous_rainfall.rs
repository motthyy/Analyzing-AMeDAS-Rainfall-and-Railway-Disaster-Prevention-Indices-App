//! 12時間無降雨リセット連続雨量の計算（docs/calculation_method.md 3節）。

pub struct ContinuousRainfallResult {
    pub continuous_rainfall_12h_mm: Vec<f64>,
    pub dry_hours: Vec<f64>,
    pub rain_event_id: Vec<f64>,
    pub state_reset_due_to_gap: Vec<bool>,
    pub warmup_flag: Vec<bool>,
}

pub fn calculate_continuous_rainfall(values: &[f64], dry_hours_reset: i64) -> ContinuousRainfallResult {
    let n = values.len();
    let mut cum = vec![f64::NAN; n];
    let mut dry = vec![f64::NAN; n];
    let mut event_id = vec![f64::NAN; n];
    let mut reset_due_to_gap = vec![false; n];
    let mut warmup = vec![false; n];

    let mut cur_cum = 0.0_f64;
    let mut cur_dry = dry_hours_reset;
    let mut cur_event_id: i64 = 0;
    let mut pending_reset = true;

    for i in 0..n {
        let val = values[i];
        if val.is_nan() {
            pending_reset = true;
            continue;
        }
        if pending_reset {
            cur_cum = 0.0;
            cur_dry = dry_hours_reset;
            warmup[i] = true;
            reset_due_to_gap[i] = true;
            pending_reset = false;
        }

        if val > 0.0 {
            if cur_dry >= dry_hours_reset {
                cur_event_id += 1;
            }
            cur_cum += val;
            cur_dry = 0;
        } else {
            cur_dry += 1;
            if cur_dry >= dry_hours_reset {
                cur_cum = 0.0;
            }
        }

        cum[i] = cur_cum;
        dry[i] = cur_dry as f64;
        event_id[i] = if cur_event_id > 0 { cur_event_id as f64 } else { f64::NAN };
    }

    ContinuousRainfallResult {
        continuous_rainfall_12h_mm: cum,
        dry_hours: dry,
        rain_event_id: event_id,
        state_reset_due_to_gap: reset_due_to_gap,
        warmup_flag: warmup,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accumulates_during_rain() {
        let r = calculate_continuous_rainfall(&[1.0, 2.0, 3.0], 12);
        assert_eq!(r.continuous_rainfall_12h_mm, vec![1.0, 3.0, 6.0]);
    }

    #[test]
    fn resets_to_zero_after_12_dry_hours() {
        let mut values = vec![5.0];
        values.extend(vec![0.0; 12]);
        let r = calculate_continuous_rainfall(&values, 12);
        assert_eq!(r.dry_hours[12], 12.0);
        assert_eq!(r.continuous_rainfall_12h_mm[12], 0.0);
    }
}
