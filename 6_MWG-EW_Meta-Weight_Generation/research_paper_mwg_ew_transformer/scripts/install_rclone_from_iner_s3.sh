#!/usr/bin/env bash
set -euo pipefail

S3_ENDPOINT="${S3_ENDPOINT:-https://iner.aihuanxin.cn}"
S3_BUCKET="${S3_BUCKET:-jtdlp-21b4208dde424e96b159362ef49c9c96}"
RCLONE_REMOTE="${RCLONE_REMOTE:-iner-aihuanxin}"
RCLONE_ZIP_KEY="${RCLONE_ZIP_KEY:-}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/bin}"
CONFIG_DIR="${RCLONE_CONFIG_DIR:-$HOME/.config/rclone}"
WORK_DIR="${WORK_DIR:-/tmp/rclone-install}"

if [[ -z "${AWS_ACCESS_KEY_ID:-}" || -z "${AWS_SECRET_ACCESS_KEY:-}" ]]; then
  cat >&2 <<'EOF'
Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script.
EOF
  exit 2
fi

mkdir -p "$WORK_DIR" "$INSTALL_DIR" "$CONFIG_DIR"
cd "$WORK_DIR"

cat > "$CONFIG_DIR/rclone.conf" <<EOF
[$RCLONE_REMOTE]
type = s3
provider = Other
access_key_id = ${AWS_ACCESS_KEY_ID}
secret_access_key = ${AWS_SECRET_ACCESS_KEY}
endpoint = ${S3_ENDPOINT}
EOF

if command -v rclone >/dev/null 2>&1; then
  RCLONE_BOOTSTRAP="$(command -v rclone)"
elif [[ -x "$INSTALL_DIR/rclone" ]]; then
  RCLONE_BOOTSTRAP="$INSTALL_DIR/rclone"
else
  echo "No existing rclone found. Downloading rclone zip via signed S3 request." >&2
  python3 - <<'PY'
import datetime
import hashlib
import hmac
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

endpoint = os.environ.get("S3_ENDPOINT", "https://iner.aihuanxin.cn").rstrip("/")
bucket = os.environ.get("S3_BUCKET", "jtdlp-21b4208dde424e96b159362ef49c9c96")
key = os.environ.get("RCLONE_ZIP_KEY", "").strip("/")
region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
access_key = os.environ["AWS_ACCESS_KEY_ID"]
secret_key = os.environ["AWS_SECRET_ACCESS_KEY"]
host = urllib.parse.urlparse(endpoint).netloc

def sign(key_bytes, msg):
    return hmac.new(key_bytes, msg.encode("utf-8"), hashlib.sha256).digest()

def signing_key(secret, date_stamp):
    k_date = sign(("AWS4" + secret).encode("utf-8"), date_stamp)
    k_region = sign(k_date, region)
    k_service = sign(k_region, "s3")
    return sign(k_service, "aws4_request")

def request(path, query="", out_path=None):
    now = datetime.datetime.utcnow()
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(b"").hexdigest()
    headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
    }
    signed_headers = ";".join(sorted(headers))
    canonical_headers = "".join(f"{name}:{headers[name]}\n" for name in sorted(headers))
    canonical_request = "\n".join(["GET", path, query, canonical_headers, signed_headers, payload_hash])
    scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    ])
    signature = hmac.new(signing_key(secret_key, date_stamp), string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    headers["Authorization"] = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    url = f"{endpoint}{path}"
    if query:
        url = f"{url}?{query}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers, method="GET"), timeout=180) as resp:
        data = resp.read()
    if out_path:
        open(out_path, "wb").write(data)
    return data

if not key:
    xml = request(f"/{bucket}", "list-type=2").decode("utf-8")
    root = ET.fromstring(xml)
    ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}
    keys = []
    for item in root.findall(".//s3:Contents", ns):
        candidate = item.findtext("s3:Key", default="", namespaces=ns)
        if re.search(r"(^|/)rclone.*linux.*\.zip$|(^|/)rclone.*\.zip$", candidate):
            keys.append(candidate)
    if not keys:
        raise SystemExit(f"No rclone*.zip found in s3://{bucket}")
    key = sorted(keys)[-1]

print(f"Downloading s3://{bucket}/{key}", file=sys.stderr)
request(f"/{bucket}/{urllib.parse.quote(key, safe='/')}", out_path="rclone.zip")
PY
  rm -rf rclone-extract
  mkdir -p rclone-extract
  unzip -q -o rclone.zip -d rclone-extract
  RCLONE_BIN="$(find rclone-extract -type f -name rclone | head -1)"
  if [[ -z "$RCLONE_BIN" ]]; then
    echo "rclone binary not found inside rclone.zip" >&2
    exit 1
  fi
  install -m 0755 "$RCLONE_BIN" "$INSTALL_DIR/rclone"
  RCLONE_BOOTSTRAP="$INSTALL_DIR/rclone"
fi

"$RCLONE_BOOTSTRAP" version
"$RCLONE_BOOTSTRAP" lsf "$RCLONE_REMOTE:$S3_BUCKET" --s3-no-check-bucket | sed -n '1,80p'

echo "rclone is ready at $RCLONE_BOOTSTRAP"
