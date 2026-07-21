//! タンクモデルのベンチマーク: Python版（約52秒/50年規模、README.md参照）との比較用。
//! 実行: cargo run --release --example benchmark

use amedas_core::soil_tank::{InitialStorageMm, TankModelConfig, TankOutlet, TankSpec};
use rand::rngs::StdRng;
use rand::{Rng, SeedableRng};
use std::time::Instant;

fn config() -> TankModelConfig {
    TankModelConfig {
        time_step_hours: 1.0 / 6.0,
        tank1: TankSpec {
            outlets: vec![
                TankOutlet { height_mm: 15.0, coefficient_per_hour: 0.10 },
                TankOutlet { height_mm: 60.0, coefficient_per_hour: 0.15 },
            ],
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

fn main() {
    let years = 50;
    let n = years * 365 * 24 * 6; // 50年分, 10分刻み
    println!("n = {n} steps ({years}年分, 10分刻み)");

    let mut rng = StdRng::seed_from_u64(2026);
    let values: Vec<f64> = (0..n)
        .map(|_| {
            let r: f64 = rng.gen();
            if r < 0.75 {
                0.0
            } else if r < 0.95 {
                rng.gen_range(0.1..2.0)
            } else {
                rng.gen_range(2.0..15.0)
            }
        })
        .collect();

    let cfg = config();
    let start = Instant::now();
    let result = amedas_core::soil_tank::run_tank_model_10min(&values, &cfg);
    let elapsed = start.elapsed();

    println!("Rustネイティブ実行時間: {:.3}秒", elapsed.as_secs_f64());
    println!("(検算用) 最終貯留量 tank1={:.4} tank2={:.4} tank3={:.4}", result.tank1_mm[n - 1], result.tank2_mm[n - 1], result.tank3_mm[n - 1]);
}
