# amedas-core（Rust計算コア）

`docs/language_migration_plan.md` のPhase 1に対応する、計算コアのRust移植版。
Python版 `src/amedas_rainfall/` の `processing/` `indices/` `statistics/` を移植している。

## 現在の状態（2026-07-21時点）

**ビルド・テスト検証済み。** Visual Studio Build Tools導入後、`cargo test`で
ユニットテスト16件・ゴールデンフィクスチャ突合テスト9件が全て成功した
（`soil_tank_matches_python`を含む）。

```powershell
cd core
cargo test
```

### ベンチマーク結果

`cargo run --release --example benchmark`（Rust）と
`.venv/Scripts/python.exe core/examples/benchmark_python.py`（Python、同一条件）を
50年分・10分刻み・262.8万ステップで比較。

| 実装 | 実行時間 |
|---|---|
| Python（`indices/soil_tank.py`） | 10.138秒 |
| Rustネイティブ（release） | 0.070秒 |

**約145倍高速化。** 「重い」の主因だったタンクモデル計算のボトルネックは、
Rust移植により実質的に解消した（WASM化後はこれよりやや遅くなる想定だが、
それでも純Pythonループとは桁違いに高速な見込み。実測はPhase 2で行う）。

## 実装済みモジュール

| モジュール | Python対応元 | 状態 |
|---|---|---|
| `normalization.rs` | `processing/normalization.py` | 0.3mm閾値処理を移植済み |
| `quality.rs` | `processing/quality.py` | 重複解決ロジック(`resolve_duplicates`)を移植済み |
| `continuous_rainfall.rs` | `indices/continuous_rainfall.py` | 12時間無降雨リセット連続雨量を移植済み |
| `rolling_rainfall.rs` | `indices/rolling_rainfall.py` | 24時間移動雨量を移植済み |
| `effective_rainfall.rs` | `indices/effective_rainfall.py` | 実効雨量（半減期減衰）を移植済み |
| `soil_tank.rs` | `indices/soil_tank.py` | 3段タンクモデル・10分雨量均等分配を移植済み（**性能改善の本丸**） |
| `annual_maxima.rs` | `statistics/annual_maxima.py` | 3種の年区切り・年最大値・完全性判定を移植済み |
| `gumbel.rs` | `statistics/gumbel.py` | 積率法（厳密一致）・最尤法（不動点反復、近似一致）・適合度評価を移植済み |
| `bootstrap.rs` | `statistics/bootstrap.py` | ブートストラップ信頼区間を移植済み（乱数系列はPython版と非互換、統計的性質のみ検証） |

## 未移植・意図的に後回しにしたもの

- `processing/merging.py`（複数ダウンロード結果の統合）: CSV取り込みパイプライン全体の
  再設計と合わせてPhase 3（データ取得層）で扱う方が自然なため、Phase 1では見送った。
  重複解決の核心ロジック自体は`quality.rs`に移植済み。
- `jma/*`（気象庁データ取得）: `docs/language_migration_plan.md` 5節の通り、TypeScript
  （Cloudflare Workers）へ移植する方針のため、Rustコアの対象外。
- 画像出力・Excel出力・Streamlit UI: Phase 3で `web/`（SvelteKit）側に実装する。

## 数値精度についての注意

- 決定論的なアルゴリズム（閾値処理・連続雨量・移動雨量・実効雨量・タンクモデル・
  年最大値・積率法ガンベル）はPython版と**ビット精度に近い一致**を目標とする
  （`tests/fixtures/golden/*.json` との突合、許容誤差1e-9〜1e-6）。
- 最尤法ガンベル（`fit_gumbel_mle`）は、SciPyの汎用最適化ルーチンではなく
  Gumbel分布のMLE方程式を不動点反復で直接解く実装のため、数学的には同じ解に
  収束するが数値的には相対誤差1e-6程度までの近似一致とする。
- ブートストラップ信頼区間は、NumPy PCG64と異なる乱数生成器を使うため、
  個々の値は一致しない。同一シードでの再現性と統計的妥当性のみを検証する。

## 次のステップ（Phase 2）

Phase 1（本クレートのビルド・テスト・ベンチマーク）は完了した。次はPhase 2、
`wasm-bindgen`によるWASM化と、SvelteKit最小UIでの実機（iPhone Safari含む）検証。

1. `wasm32-unknown-unknown`ターゲットを使い、`lib.rs`に`#[wasm_bindgen]`エクスポートを追加する。
2. `web/`にSvelteKit（static adapter）プロジェクトを新規作成し、WASMモジュールを
   読み込んで「データ読み込み→指標計算→Plotlyグラフ表示」のみの最小UIを作る。
3. モバイルSafari（iOS 16.4以降）でOPFS・WASMの動作を実機検証する。
4. 問題なければPhase 3（全画面移植・JMAプロキシ実装）へ進む。
