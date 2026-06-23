#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="${PADDLEOCR_HOME:-/root/.paddleocr/whl}"

download_and_extract() {
  local url="$1"
  local target_dir="$2"
  local archive_name="$3"

  mkdir -p "$target_dir"
  cd "$target_dir"

  if [ -f "inference.pdmodel" ] && [ -f "inference.pdiparams" ]; then
    echo "OK: $target_dir already has OCR model files"
    return 0
  fi

  echo "Downloading $archive_name"
  if command -v curl >/dev/null 2>&1; then
    curl -L --retry 3 --fail "$url" -o "$archive_name"
  else
    python - "$url" "$archive_name" <<'PY'
import sys
import urllib.request

url, output = sys.argv[1], sys.argv[2]
for attempt in range(1, 4):
    try:
        urllib.request.urlretrieve(url, output)
        break
    except Exception:
        if attempt == 3:
            raise
PY
  fi
  tar -xf "$archive_name" --strip-components=1
  test -f "inference.pdmodel"
  test -f "inference.pdiparams"
  echo "OK: installed $target_dir"
}

download_and_extract \
  "https://paddleocr.bj.bcebos.com/PP-OCRv3/multilingual/Multilingual_PP-OCRv3_det_infer.tar" \
  "$BASE_DIR/det/ml/Multilingual_PP-OCRv3_det_infer" \
  "Multilingual_PP-OCRv3_det_infer.tar"

download_and_extract \
  "https://paddleocr.bj.bcebos.com/PP-OCRv4/multilingual/japan_PP-OCRv4_rec_infer.tar" \
  "$BASE_DIR/rec/japan/japan_PP-OCRv4_rec_infer" \
  "japan_PP-OCRv4_rec_infer.tar"

download_and_extract \
  "https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar" \
  "$BASE_DIR/cls/ch_ppocr_mobile_v2.0_cls_infer" \
  "ch_ppocr_mobile_v2.0_cls_infer.tar"

echo "PaddleOCR Japanese models are ready."
