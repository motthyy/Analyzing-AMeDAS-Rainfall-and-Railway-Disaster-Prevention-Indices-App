//! 推定10分雨量と気象庁標準3段タンクモデルによる推定土壌雨量指数の計算
//! （docs/calculation_method.md 6節・7節）。
//!
//! 移行の主目的: Python版（純Pythonのforループ、数十年分で約52秒）を
//! コンパイル言語に置き換えて高速化する、性能上の最重要モジュール。

use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct TankOutlet {
    pub height_mm: f64,
    pub coefficient_per_hour: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TankSpec {
    pub outlets: Vec<TankOutlet>,
    pub infiltration_coefficient_per_hour: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct InitialStorageMm {
    pub tank1: f64,
    pub tank2: f64,
    pub tank3: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct TankModelConfig {
    pub time_step_hours: f64,
    pub tank1: TankSpec,
    pub tank2: TankSpec,
    pub tank3: TankSpec,
    pub initial_storage_mm: InitialStorageMm,
}

pub struct TankModelResult {
    pub tank1_mm: Vec<f64>,
    pub tank2_mm: Vec<f64>,
    pub tank3_mm: Vec<f64>,
    pub tank1_outflow_mm: Vec<f64>,
    pub tank2_outflow_mm: Vec<f64>,
    pub tank3_outflow_mm: Vec<f64>,
    pub tank1_infiltration_mm: Vec<f64>,
    pub tank2_infiltration_mm: Vec<f64>,
    pub tank3_infiltration_mm: Vec<f64>,
}

/// 閾値処理後時雨量を10分雨量へ均等分配する（1時間雨量を6等分）。
/// 欠測(NaN)の時間は6個ともNaNとする。
pub fn disaggregate_hourly_to_10min(hourly_mm: &[f64]) -> Vec<f64> {
    let mut out = Vec::with_capacity(hourly_mm.len() * 6);
    for &v in hourly_mm {
        let part = if v.is_nan() { f64::NAN } else { v / 6.0 };
        for _ in 0..6 {
            out.push(part);
        }
    }
    out
}

fn side_outflow_mm(storage_mm: f64, spec: &TankSpec, dt_hours: f64) -> f64 {
    spec.outlets
        .iter()
        .map(|o| {
            if storage_mm > o.height_mm {
                o.coefficient_per_hour * (storage_mm - o.height_mm) * dt_hours
            } else {
                0.0
            }
        })
        .sum()
}

fn infiltration_mm(storage_mm: f64, spec: &TankSpec, dt_hours: f64) -> f64 {
    spec.infiltration_coefficient_per_hour * storage_mm * dt_hours
}

/// 10分刻みで3段タンクモデルを実行する。
///
/// Python版 (`indices/soil_tank.py::run_tank_model_10min`) と1対1で対応する。
/// 各タンクについて、(1)入力を加算→(2)側方流出量・浸透量を計算→
/// (3)貯留量から両方を差し引く（0未満にならないようクリップ）、の順で計算する。
/// 欠測(NaN)の直後の最初の有効値で、3タンクとも初期貯留量から再初期化する。
pub fn run_tank_model_10min(rainfall_10min_mm: &[f64], config: &TankModelConfig) -> TankModelResult {
    let n = rainfall_10min_mm.len();
    let dt = config.time_step_hours;

    let mut s1 = vec![f64::NAN; n];
    let mut s2 = vec![f64::NAN; n];
    let mut s3 = vec![f64::NAN; n];
    let mut out1v = vec![f64::NAN; n];
    let mut out2v = vec![f64::NAN; n];
    let mut out3v = vec![f64::NAN; n];
    let mut infil1v = vec![f64::NAN; n];
    let mut infil2v = vec![f64::NAN; n];
    let mut infil3v = vec![f64::NAN; n];

    let mut cur1 = config.initial_storage_mm.tank1;
    let mut cur2 = config.initial_storage_mm.tank2;
    let mut cur3 = config.initial_storage_mm.tank3;
    let mut pending_reset = true;

    for i in 0..n {
        let rain = rainfall_10min_mm[i];
        if rain.is_nan() {
            pending_reset = true;
            continue;
        }
        if pending_reset {
            cur1 = config.initial_storage_mm.tank1;
            cur2 = config.initial_storage_mm.tank2;
            cur3 = config.initial_storage_mm.tank3;
            pending_reset = false;
        }

        let storage1 = cur1 + rain;
        let out1 = side_outflow_mm(storage1, &config.tank1, dt);
        let inf1 = infiltration_mm(storage1, &config.tank1, dt);
        cur1 = (storage1 - out1 - inf1).max(0.0);

        let storage2 = cur2 + inf1;
        let out2 = side_outflow_mm(storage2, &config.tank2, dt);
        let inf2 = infiltration_mm(storage2, &config.tank2, dt);
        cur2 = (storage2 - out2 - inf2).max(0.0);

        let storage3 = cur3 + inf2;
        let out3 = side_outflow_mm(storage3, &config.tank3, dt);
        let inf3 = infiltration_mm(storage3, &config.tank3, dt);
        cur3 = (storage3 - out3 - inf3).max(0.0);

        s1[i] = cur1;
        s2[i] = cur2;
        s3[i] = cur3;
        out1v[i] = out1;
        out2v[i] = out2;
        out3v[i] = out3;
        infil1v[i] = inf1;
        infil2v[i] = inf2;
        infil3v[i] = inf3;
    }

    TankModelResult {
        tank1_mm: s1,
        tank2_mm: s2,
        tank3_mm: s3,
        tank1_outflow_mm: out1v,
        tank2_outflow_mm: out2v,
        tank3_outflow_mm: out3v,
        tank1_infiltration_mm: infil1v,
        tank2_infiltration_mm: infil2v,
        tank3_infiltration_mm: infil3v,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_config() -> TankModelConfig {
        TankModelConfig {
            time_step_hours: 1.0 / 6.0,
            tank1: TankSpec {
                outlets: vec![TankOutlet { height_mm: 15.0, coefficient_per_hour: 0.1 }],
                infiltration_coefficient_per_hour: 0.12,
            },
            tank2: TankSpec {
                outlets: vec![TankOutlet { height_mm: 15.0, coefficient_per_hour: 0.05 }],
                infiltration_coefficient_per_hour: 0.05,
            },
            tank3: TankSpec {
                outlets: vec![TankOutlet { height_mm: 15.0, coefficient_per_hour: 0.01 }],
                infiltration_coefficient_per_hour: 0.01,
            },
            initial_storage_mm: InitialStorageMm { tank1: 0.0, tank2: 0.0, tank3: 0.0 },
        }
    }

    #[test]
    fn known_hand_calculation_single_step() {
        let config = test_config();
        let result = run_tank_model_10min(&[10.0], &config);
        let dt = 1.0 / 6.0;
        let expected_infil1 = 0.12 * 10.0 * dt;
        let expected_tank1 = 10.0 - expected_infil1;
        assert!((result.tank1_mm[0] - expected_tank1).abs() < 1e-12);
    }

    #[test]
    fn storage_never_negative() {
        let config = test_config();
        let values = vec![0.0, 1.0, 5.0, 20.0, 0.0, 0.0];
        let result = run_tank_model_10min(&values, &config);
        assert!(result.tank1_mm.iter().all(|&v| v >= 0.0));
        assert!(result.tank2_mm.iter().all(|&v| v >= 0.0));
        assert!(result.tank3_mm.iter().all(|&v| v >= 0.0));
    }
}
