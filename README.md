# OpenWrt APK Feed

A signed OpenWrt 25.12+ APK v3 feed, published on GitHub Pages from independently maintained GitHub source repositories.

**Package source:** [nieaowei/gl-sdk4-ui-momo](https://github.com/nieaowei/gl-sdk4-ui-momo)

**Central feed:** [nieaowei/openwrt-packages](https://github.com/nieaowei/openwrt-packages)

## How it works

```text
nieaowei/gl-sdk4-ui-momo (source, Makefile, scripts/build-apk.sh)
                      |
           sources.json + scheduled GitHub Actions
                      |
          1. checkout source repository
          2. run source build script (NO signing key)
          3. collect .apk build artifacts
                      |
       separate signing + GitHub Pages job
          4. re-sign .apk files with feed key
          5. produce signed packages.adb
          6. publish feed to GitHub Pages
```

APK files do **not** have to be committed to the central repository and source repositories do **not** need Releases or their own GitHub Actions. The example source repository directly produces APKv3 `noarch` packages through `sh scripts/build-apk.sh`.

- Automatic source checks: every six hours (UTC, subject to GitHub Actions scheduling).
- Manual run: **Actions → Publish OpenWrt APK feed → Run workflow**.
- Changes in this repository's manifest, scripts, manual APKs, or workflow also trigger a run.
- Optional immediate cross-repository trigger: the workflow accepts `repository_dispatch` event type `source-updated`; calling the dispatch API requires a token with appropriate access to this feed repository.

## First-time setup

1. Create an ECDSA P-256 signing private key on your own trusted machine:
   ```sh
   openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem
   ```
2. Add the complete `private-key.pem` text to **Settings → Secrets and variables → Actions → New repository secret**, named **`APK_SIGNING_PRIVATE_KEY`**. Do **not** commit the private key to any repository.
3. Go to **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
4. Manually run the publish workflow (or let the scheduled run execute), and confirm that it succeeded under **Actions**.

The signing key is used *only in the publishing job*. Independently maintained source build scripts run in a preceding job without this key.

## Add more standalone repositories

Edit [sources.json](sources.json) and append an entry to the `sources` array. Example:

```json
{
  "repository": "nieaowei/gl-sdk4-ui-momo",
  "ref": "main",
  "mode": "build",
  "script": "scripts/build-apk.sh",
  "artifact_glob": "dist/*.apk",
  "series": "25.12",
  "architectures": ["aarch64_cortex-a53"]
}
```

`repository` is the standalone source repository; `ref` is its branch or tag; `script` is the shell build script run from the checked-out source; `artifact_glob` selects the generated APKs. Current mode is `build`, not GitHub Releases ingestion. To support more targets, add the appropriate OpenWrt package architecture(s). `noarch` packages can be included in a per-architecture feed, but arch-specific compiled packages must match their target and release/ABI.

Current `gl-sdk4-ui-momo` is a GL.iNet SDK4 UI plugin requiring `gl-sdk4-ui-core`, `gl-oui-rpc`, `momo`, and other dependencies. Its presence in this feed does **not** make it compatible with arbitrary OpenWrt devices; use a compatible GL.iNet SDK4 firmware.

The central repository can also contain manually supplied packages in `packages/<series>/<architecture>/*.apk`.

## Feed URL and router setup

After a successful Pages deployment:

- Landing page: <https://nieaowei.github.io/openwrt-packages/>
- Public signing key: <https://nieaowei.github.io/openwrt-packages/public-key.pem>
- Architecture feed: <https://nieaowei.github.io/openwrt-packages/25.12/packages/aarch64_cortex-a53/packages.adb>

On a compatible OpenWrt 25.12+ device:

```sh
arch="$(apk --print-arch)"
echo "OpenWrt APK architecture: $arch"

mkdir -p /etc/apk/keys /etc/apk/repositories.d
wget -O /etc/apk/keys/nieaowei.pem \
  https://nieaowei.github.io/openwrt-packages/public-key.pem

echo "https://nieaowei.github.io/openwrt-packages/25.12/packages/$arch/packages.adb" \
  > /etc/apk/repositories.d/nieaowei.list

apk update
apk add gl-sdk4-ui-momo
```

The feed URL must point to a signed `packages.adb`, **not** an OPKG `Packages.gz` file. The signing public key must be imported before updating. Keep vendor/official repositories configured so dependencies can be resolved. Avoid a blanket `apk upgrade` of a vendor-modified OpenWrt system.

## Architecture and signing details

`sources.json` determines where each built APK is published: `25.12/packages/<architecture>/`. The publish step copies each file to its canonical `<name>-<version>.apk` name, signs packages with `apk adbsign`, generates `packages.adb` with `apk mkndx`, signs and verifies indexes, and uploads to GitHub Pages. The tooling comes from the checksum-verified official OpenWrt 25.12.6 mediatek/filogic SDK.

This setup indexes user packages only; kernel modules require a different kernel-version-specific feed and are not included. Public GitHub Pages has limits on site and file size; it may not suit large binary archives.

Do not run builds for untrusted external repositories without reviewing their scripts: the collection job executes source code in GitHub Actions, albeit **without the feed signing secret**.
