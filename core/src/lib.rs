//! アメダス長期雨量・鉄道防災指標解析アプリの計算コア（Rust移植版）。
//!
//! Python版 `src/amedas_rainfall/` の processing/indices/statistics を移植する。
//! 仕様の一次情報源は `docs/calculation_method.md`。

pub mod annual_maxima;
pub mod bootstrap;
pub mod continuous_rainfall;
pub mod effective_rainfall;
pub mod gumbel;
pub mod normalization;
pub mod quality;
pub mod rolling_rainfall;
pub mod soil_tank;
