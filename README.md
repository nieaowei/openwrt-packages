# OpenWrt APK v3 Feed

Signed OpenWrt 25.12+ APK feed, built from **prebuilt APKs on independent plugin repositories' GitHub Releases**, hosted by GitHub Pages.

- **Source package:** [nieaowei/gl-sdk4-ui-momo](https://github.com/nieaowei/gl-sdk4-ui-momo)
- **Source release:** [gl-sdk4-ui-momo/releases/latest](https://github.com/nieaowei/gl-sdk4-ui-momo/releases/latest)
- **Central feed:** [nieaowei/openwrt-packages](https://github.com/nieaowei/openwrt-packages)
- **Published feed:** <https://nieaowei.github.io/openwrt-packages/>

## Independent build architecture

```text
gl-sdk4-ui-momo (and other standalone plugin repositories)
  └── GitHub Actions: test -> build *.apk -> sha256 -> GitHub Release
                                    |
openwrt-packages (NO source builds)  |
  ├── sources.json -----------------+
  ├── fetch latest stable Release assets
  ├── verify *.apk.sha256 against downloaded APK
  ├── collect APKs into 25.12 / package architecture directories
  ├── sign packages using central feed private key
  ├── create and sign packages.adb with official OpenWrt SDK apk-tools v3
  └── publish GitHub Pages over HTTPS
```

The central repository **does not clone plugin source repositories, execute their build scripts, or compile their APKs**.

## Adding new plugin repositories

Add a new entry to [sources.json](sources.json), e.g.:

```json
{
  "repository": "nieaowei/gl-sdk4-ui-momo",
  "mode": "release",
  "release": "latest",
  "assets": ["gl-sdk4-ui-momo-*.apk"],
  "series": "25.12",
  "architectures": ["aarch64_cortex-a53"]
}
```

Each plugin repo should independently publish a stable GitHub Release with matching `*.apk` and `*.apk.sha256` assets. The central collector requires the SHA256 file for every APK. `release` can be `latest` or a pinned tag such as `v1.3.0-r1`; `assets` is a list of filename glob patterns.

Any source-specific build requirements (OpenWrt SDK, Rust, Go, GL.iNet SDK4, and so on) belong in the **plugin repository's Actions**. Never copy the signing private key to plugin repositories.

The current source package is an architecture-independent `noarch` GL.iNet SDK4 UI plugin. It is included in an `aarch64_cortex-a53` feed for the GL-MT3600BE setup; dependencies such as `momo` and `gl-sdk4-ui-core` must already be available from suitable package feeds.

## Scheduling and triggers

- Central Actions checks GitHub Releases every **6 hours** (GitHub cron scheduling is approximate).
- You can republish immediately via [Actions → Publish OpenWrt APK feed → Run workflow](https://github.com/nieaowei/openwrt-packages/actions/workflows/publish-apk.yml).
- Optional `repository_dispatch` event type `source-updated` is supported if you later configure an appropriate cross-repository token. No cross-repository token is needed for the scheduled collector.
- Changes to the central manifest, workflows, scripts, or manually checked-in APKs trigger a central republish.

Collecting from GitHub Release assets avoids downloading the plugin sources and rebuilding on every central run. Source releases should be immutable: **bump the source package version or release number before publishing changed installable contents**.

## Central signing key

Configure `APK_SIGNING_PRIVATE_KEY` in **central repo Settings → Secrets and variables → Actions**:

```sh
openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem
```

Store the *entire PEM private key* as that GitHub repository secret. Do not commit it. Set **Settings → Pages → Source** to **GitHub Actions**. The publish job signs both APK files and the `packages.adb` index, verifies signatures, and exposes the public key at <https://nieaowei.github.io/openwrt-packages/public-key.pem>.

The collector uses only GitHub public Releases and SHA256 checksums. The checksums detect accidental corruption and mismatched assets, not a malicious update from a compromised upstream repo. Audit repos you add because the central job signs their published APKs.

## Install on OpenWrt 25.12+

Published feed index:

```text
https://nieaowei.github.io/openwrt-packages/25.12/packages/aarch64_cortex-a53/packages.adb
```

On a compatible device:

```sh
arch="$(apk --print-arch)"
mkdir -p /etc/apk/keys /etc/apk/repositories.d
wget -O /etc/apk/keys/nieaowei.pem \
  https://nieaowei.github.io/openwrt-packages/public-key.pem
echo "https://nieaowei.github.io/openwrt-packages/25.12/packages/$arch/packages.adb" \
  > /etc/apk/repositories.d/nieaowei.list
apk update
apk add gl-sdk4-ui-momo
```

Do not use this feed with a different architecture or an incompatible GL.iNet SDK4 firmware. Keep the original dependency feeds enabled and do not blindly `apk upgrade` the entire system.

## Verification and traceability

The central workflow downloads each Release APK and its companion SHA256 file, checks the digest before repackaging, signs packages and indexes, and publishes `sources.json` at the Pages site containing the originating repository, Release tag, asset name and original SHA256.

You can manually add APKs at `packages/<series>/<arch>/*.apk` if needed. Kernel modules require kernel-build-specific repositories and are not handled here. GitHub Pages size/bandwidth limitations apply.
