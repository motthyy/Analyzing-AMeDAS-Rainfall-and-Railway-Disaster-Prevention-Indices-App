"""install.bat から呼び出される、Windows証明書ストア由来のCAバンドル生成スクリプト。

社内SSLインスペクションプロキシ(Zscaler等)配下では、pipが標準で使う
certifi同梱のCA一覧だけではPyPIへのアクセスが
``CERTIFICATE_VERIFY_FAILED`` で失敗する。install.batが通常のpip installに
失敗した場合のフォールバックとして本スクリプトを実行し、Windows証明書
ストアから生成したPEMバンドルのパスを標準出力へ書き出す
(``amedas_rainfall.jma.ca_bundle`` の薄いラッパー)。

requirements.txtのインストール前でも実行できるよう、標準ライブラリのみに
依存する ``amedas_rainfall.jma.ca_bundle`` だけをインポートする。
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from amedas_rainfall.jma.ca_bundle import ensure_ca_bundle_path  # noqa: E402


def main() -> int:
    bundle_path = ensure_ca_bundle_path()
    if bundle_path is None:
        return 1
    sys.stdout.write(bundle_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
