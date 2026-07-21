//! 品質情報に基づく重複時刻の解決ロジック（docs/calculation_method.md 2節）。
//!
//! merging.py（複数ダウンロード結果の時系列統合）は、CSV取り込みパイプライン全体の
//! 再設計にあわせてPhase3（データ取得層の移植）で扱う。ここでは統合ロジックの核心である
//! 重複解決（resolve_duplicates相当）のみを移植する。

#[derive(Debug, Clone)]
pub struct CandidateRecord {
    pub rainfall_raw_mm: Option<f64>,
    pub quality_code: Option<String>,
    pub homogeneity_number: Option<i64>,
    pub source_file: String,
}

#[derive(Debug, Clone)]
pub struct ResolvedRecord {
    pub rainfall_raw_mm: Option<f64>,
    pub quality_code: Option<String>,
    pub homogeneity_number: Option<i64>,
    pub source_file: String,
    pub is_conflicting: bool,
    pub conflict_candidates: Vec<CandidateRecord>,
}

fn tier(quality_code: &Option<String>) -> i32 {
    match quality_code.as_deref() {
        Some("8") => 2,
        Some("5") | Some("4") | Some("2") => 1,
        Some("1") | Some("0") => 0,
        _ => -1,
    }
}

/// 同一時刻に複数の観測値候補がある場合、品質情報に基づき1件へ解決する。
/// 優先順位: 1.正常品質値 2.準正常値 3.欠測値。
/// 品質が同一で値が異なる場合は競合として記録し、黙って上書きしない
/// （先勝ちで代表値を選ぶが、is_conflicting=trueを立てて呼び出し側に通知する）。
pub fn resolve_duplicates(candidates: &[CandidateRecord]) -> ResolvedRecord {
    assert!(!candidates.is_empty(), "候補が空です。");
    if candidates.len() == 1 {
        let c = &candidates[0];
        return ResolvedRecord {
            rainfall_raw_mm: c.rainfall_raw_mm,
            quality_code: c.quality_code.clone(),
            homogeneity_number: c.homogeneity_number,
            source_file: c.source_file.clone(),
            is_conflicting: false,
            conflict_candidates: vec![],
        };
    }

    let best_tier = candidates.iter().map(|c| tier(&c.quality_code)).max().unwrap();
    let top_candidates: Vec<CandidateRecord> = candidates
        .iter()
        .filter(|c| tier(&c.quality_code) == best_tier)
        .cloned()
        .collect();

    // NaNはビット表現で比較できないため、bits化して distinct 判定する
    // （気象庁データのrainfall_raw_mmは通常NaNではなくOptionのNoneで欠測を表すため実務上は問題にならない）。
    let mut distinct: Vec<Option<u64>> = top_candidates
        .iter()
        .map(|c| c.rainfall_raw_mm.map(|v| v.to_bits()))
        .collect();
    distinct.sort();
    distinct.dedup();
    let is_conflicting = distinct.len() > 1;

    let chosen = &top_candidates[0];
    ResolvedRecord {
        rainfall_raw_mm: chosen.rainfall_raw_mm,
        quality_code: chosen.quality_code.clone(),
        homogeneity_number: chosen.homogeneity_number,
        source_file: chosen.source_file.clone(),
        is_conflicting,
        conflict_candidates: if is_conflicting { top_candidates } else { vec![] },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn candidate(value: f64, quality: &str) -> CandidateRecord {
        CandidateRecord {
            rainfall_raw_mm: Some(value),
            quality_code: Some(quality.to_string()),
            homogeneity_number: Some(1),
            source_file: "f.csv".to_string(),
        }
    }

    #[test]
    fn normal_quality_wins_over_missing() {
        let candidates = vec![candidate(1.0, "1"), candidate(2.0, "8")];
        let resolved = resolve_duplicates(&candidates);
        assert_eq!(resolved.rainfall_raw_mm, Some(2.0));
        assert!(!resolved.is_conflicting);
    }

    #[test]
    fn same_tier_different_value_is_conflicting() {
        let candidates = vec![candidate(1.0, "8"), candidate(2.0, "8")];
        let resolved = resolve_duplicates(&candidates);
        assert!(resolved.is_conflicting);
    }
}
