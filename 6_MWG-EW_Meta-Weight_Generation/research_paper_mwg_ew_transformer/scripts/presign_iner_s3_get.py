#!/usr/bin/env python3
"""Generate a SigV4 presigned GET URL for the INER Huanxin S3 endpoint."""

from __future__ import annotations

import argparse
import configparser
import datetime as dt
import hashlib
import hmac
import pathlib
import urllib.parse


def sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def quote(value: str) -> str:
    return urllib.parse.quote(value, safe="-_.~")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bucket")
    parser.add_argument("key")
    parser.add_argument("--remote", default="iner-aihuanxin")
    parser.add_argument("--config", default=str(pathlib.Path.home() / ".config/rclone/rclone.conf"))
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--expires", type=int, default=3600)
    args = parser.parse_args()

    cfg = configparser.ConfigParser()
    cfg.read(args.config)
    section = cfg[args.remote]
    access_key = section["access_key_id"]
    secret_key = section["secret_access_key"]
    endpoint = section["endpoint"].rstrip("/")
    host = urllib.parse.urlparse(endpoint).netloc

    now = dt.datetime.now(dt.timezone.utc)
    date = now.strftime("%Y%m%d")
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    scope = f"{date}/{args.region}/s3/aws4_request"
    canonical_uri = "/" + "/".join(quote(part) for part in [args.bucket, *args.key.split("/")])
    credential = f"{access_key}/{scope}"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
        "X-Amz-Credential": credential,
        "X-Amz-Date": amz_date,
        "X-Amz-Expires": str(args.expires),
        "X-Amz-SignedHeaders": "host",
    }
    canonical_query = "&".join(f"{quote(k)}={quote(v)}" for k, v in sorted(params.items()))
    canonical_request = "\n".join(
        [
            "GET",
            canonical_uri,
            canonical_query,
            f"host:{host}",
            "",
            "host",
            "UNSIGNED-PAYLOAD",
        ]
    )
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )
    signing_key = sign(sign(sign(sign(("AWS4" + secret_key).encode("utf-8"), date), args.region), "s3"), "aws4_request")
    signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    print(f"{endpoint}{canonical_uri}?{canonical_query}&X-Amz-Signature={signature}")


if __name__ == "__main__":
    main()
