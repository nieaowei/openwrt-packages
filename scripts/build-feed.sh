#!/usr/bin/env bash
# Build a signed APK v3 feed from packages/<series>/<arch>/*.apk.
set -euo pipefail

: "${APK_BIN:?Set APK_BIN to the OpenWrt SDK host apk executable}"
: "${SIGNING_KEY:?Set SIGNING_KEY to the absolute PEM private-key path}"
: "${SITE_DIR:?Set SITE_DIR to the output directory}"

root="$(cd "$(dirname "$0")/.." && pwd)"
input="${PACKAGES_DIR:-$root/packages}"
if [ ! -d "$input" ]; then
  echo "Package input directory does not exist: $input" >&2
  exit 1
fi
mkdir -p "$SITE_DIR"
site="$(cd "$SITE_DIR" && pwd)"
keys="$site/.keys"
mkdir -p "$keys"
openssl ec -in "$SIGNING_KEY" -pubout -out "$site/public-key.pem"
cp "$site/public-key.pem" "$keys/public-key.pem"

total=0
while IFS= read -r -d '' source; do
  rel="${source#"$input"/}"
  series="$(printf '%s' "$rel" | cut -d/ -f1)"
  arch="$(printf '%s' "$rel" | cut -d/ -f2)"
  filename="$(printf '%s' "$rel" | cut -d/ -f3)"

  if [[ "$rel" != "$series/$arch/$filename" ]] || [[ ! "$series" =~ ^[0-9]+\.[0-9]+$ ]] || [[ ! "$arch" =~ ^[A-Za-z0-9_]+$ ]]; then
    echo "Invalid package path: $source (expected packages/<series>/<arch>/<file>.apk)" >&2
    exit 1
  fi

  read -r pkg_name pkg_version < <(
    "$APK_BIN" --allow-untrusted adbdump "$source" | awk '
      /^info:/ { inside=1; next }
      /^[^ ]/ { inside=0 }
      inside && $1=="name:" { name=$2 }
      inside && $1=="version:" { version=$2 }
      END { print name, version }'
  )
  if [[ ! "$pkg_name" =~ ^[A-Za-z0-9._+~-]+$ ]] || [[ ! "$pkg_version" =~ ^[A-Za-z0-9._+~-]+$ ]]; then
    echo "Unable to parse safe package name and version from: $source" >&2
    exit 1
  fi

  dest_dir="$site/$series/packages/$arch"
  mkdir -p "$dest_dir"
  dest="$dest_dir/$pkg_name-$pkg_version.apk"
  if [[ -e "$dest" ]]; then
    echo "Duplicate package: $dest" >&2
    exit 1
  fi
  cp "$source" "$dest"
  "$APK_BIN" --allow-untrusted adbsign --sign-key "$SIGNING_KEY" --reset-signatures "$dest"
  "$APK_BIN" --keys-dir "$keys" verify "$dest"
  total=$((total+1))
done < <(find "$input" -type f -name '*.apk' -print0 | sort -z)

if (( total == 0 )); then
  echo "No APKs in $input/<series>/<arch>/; nothing to publish" >&2
  exit 1
fi

while IFS= read -r dir; do
  (
    cd "$dir"
    "$APK_BIN" --keys-dir "$keys" mkndx --output packages.adb --description "nieaowei OpenWrt APK feed" ./*.apk
    "$APK_BIN" --allow-untrusted adbsign --sign-key "$SIGNING_KEY" --reset-signatures packages.adb
    "$APK_BIN" --keys-dir "$keys" verify packages.adb
  )
done < <(find "$site" -type f -name '*.apk' -printf '%h\n' | sort -u)

# Never put copies of any signing key into the published Pages artifact.
rm -rf "$keys"
touch "$site/.nojekyll"

{
  cat <<'HTML'
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><title>nieaowei OpenWrt APK Feed</title></head>
<body>
<h1>nieaowei OpenWrt APK Feed</h1>
<p>OpenWrt 25.12+ APK v3 repository. Import <a href="public-key.pem">public-key.pem</a> before use.</p>
<ul>
HTML
  while IFS= read -r index; do
    relative="${index#"$site"/}"
    printf '<li><a href="%s">%s</a></li>\n' "$relative" "$relative"
  done < <(find "$site" -name packages.adb -type f | sort)
  cat <<'HTML'
</ul>
<p>Packages may depend on a particular OpenWrt release, architecture or kernel.</p>
</body></html>
HTML
} > "$site/index.html"
echo "Created $total signed package(s) and signed indexes"
