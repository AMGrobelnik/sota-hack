#!/usr/bin/env bash
# Resumable download of the Helsinki neonatal EEG record (Zenodo 4940267) with md5 checks.
# Usage: download.sh <manifest.tsv> <data_dir> <first_n_babies|all>
# The manifest has one line per file: name<TAB>size<TAB>md5<TAB>url.
set -u
manifest="${1:?manifest}"
data="${2:?data dir}"
limit="${3:?first n babies or all}"
mkdir -p "$data"
fail=0
fsize() { if [[ -f "$1" ]]; then echo $(( $(wc -c < "$1") )); else echo 0; fi; }
while IFS=$'\t' read -r name size md5 url; do
  if [[ "$name" == eeg*.edf ]]; then
    n="${name#eeg}"; n="${n%.edf}"
    if [[ "$limit" != "all" && "$n" -gt "$limit" ]]; then continue; fi
  elif [[ "$name" != annotations_2017_*.csv && "$name" != clinical_information.csv ]]; then
    continue
  fi
  out="$data/$name"
  if [[ -f "$out" ]] && [[ "$(fsize "$out")" == "$size" ]] && [[ "$(md5 -q "$out")" == "$md5" ]]; then
    echo "ok-cached $name"; continue
  fi
  for attempt in 1 2 3; do
    curl -sS -L -C - --retry 3 --max-time 1800 -o "$out" "$url"
    if [[ "$(fsize "$out")" == "$size" ]] && [[ "$(md5 -q "$out")" == "$md5" ]]; then
      echo "ok $name $size"; break
    fi
    if [[ "$(fsize "$out")" -ge "$size" ]]; then rm -f "${out:?}"; fi
    echo "retry $name attempt $attempt"
    if [[ "$attempt" == 3 ]]; then echo "FAILED $name"; fail=1; fi
  done
done < "$manifest"
echo "DOWNLOAD-DONE fail=$fail"
