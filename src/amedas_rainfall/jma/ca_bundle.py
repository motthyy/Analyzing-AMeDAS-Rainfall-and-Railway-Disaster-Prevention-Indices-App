"""社内SSLインスペクションプロキシ(Zscaler等)配下でも気象庁サイトへの
アクセスが通るようにするための、OS証明書ストア連携ユーティリティ。

企業ネットワークではHTTPS通信がプロキシによって中間者検査され、プロキシ
自身のルート証明書で再署名されることが多い。この証明書はWindowsの
「信頼されたルート証明機関」ストアには登録されているが、Pythonの
``requests`` やPlaywrightが起動するNode.jsドライバは既定でこれを信頼せず、
``CERTIFICATE_VERIFY_FAILED`` で失敗する。

本モジュールはWindows証明書ストアの内容をPEMファイルへ書き出し、
``requests`` (``Session.verify``) やPlaywright (``NODE_EXTRA_CA_CERTS``)
から参照できるようにする。プロキシが存在しない/Windows以外の環境では
何もせず、各ライブラリ標準の検証（certifi同梱のCA一覧）に委ねる。
"""

from __future__ import annotations

import logging
import ssl
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_BUNDLE_PATH = Path(tempfile.gettempdir()) / "amedas_rainfall_windows_ca_bundle.pem"


def _windows_root_store_pem() -> str:
    """Windows証明書ストア(ROOT/CA)の内容をPEM文字列として返す。

    Windows以外、またはストアへアクセスできない場合は空文字列を返す。
    """
    if not hasattr(ssl, "enum_certificates"):
        return ""
    seen: set[bytes] = set()
    pem_blocks: list[str] = []
    for store_name in ("ROOT", "CA"):
        try:
            entries = ssl.enum_certificates(store_name)
        except OSError:
            continue
        for der_bytes, encoding, _trust in entries:
            if encoding != "x509_asn" or der_bytes in seen:
                continue
            seen.add(der_bytes)
            pem_blocks.append(ssl.DER_cert_to_PEM_cert(der_bytes))
    return "".join(pem_blocks)


def ensure_ca_bundle_path() -> str | None:
    """Windows証明書ストアから生成したPEMバンドルのパスを返す。

    呼び出しのたびにストアの最新内容で書き直すため、プロキシの証明書が
    更新された場合も次回接続時から反映される。バンドルを作成できなかった
    場合(非Windows環境等)は ``None`` を返し、呼び出し側は標準の検証
    (certifi)にフォールバックすること。
    """
    pem_text = _windows_root_store_pem()
    if not pem_text:
        return None
    try:
        _BUNDLE_PATH.write_text(pem_text, encoding="ascii")
    except OSError:
        logger.warning("Windows証明書ストアのPEMバンドル書き出しに失敗しました。", exc_info=True)
        return None
    return str(_BUNDLE_PATH)
