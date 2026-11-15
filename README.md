# OpenWrt APK Feed

A GitHub Pages-hosted, signed OpenWrt 25.12+ APK v3 repository.

## Setup

1. Generate a signing key **locally** (keep the private key secret):
   ```sh
   openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem
   ```
2. In this repository's **Settings → Secrets and variables → Actions**, create a repository secret named `APK_SIGNING_PRIVATE_KEY`. Paste the entire PEM contents of `private-key.pem`. **Never commit this key.**
3. In **Settings → Pages**, set **Build and deployment → Source** to **GitHub Actions**.
4. Add prebuilt OpenWrt APK v3 files to `packages/<series>/<arch>/` (for example, `packages/25.12/aarch64_cortex-a53/example-1.0-r1.apk`), then commit and push to `main`. Alternatively, run **Actions → Publish OpenWrt APK feed → Run workflow**.

The GitHub Action downloads the *official OpenWrt 25.12.6 mediatek/filogic SDK* to obtain apk-tools v3 (only a host-side packaging tool). It reads the actual name/version from each APK, copies the APK to its canonical `name-version.apk` filename, re-signs the copy, creates a signed `packages.adb`, and deploys the feed. It does **not** compile packages. The published public key is at:

```text
https://nieaowei.github.io/openwrt-packages/public-key.pem
```

The repository index for an `aarch64_cortex-a53` package is:

```text
https://nieaowei.github.io/openwrt-packages/25.12/packages/aarch64_cortex-a53/packages.adb
```

## Router setup

On OpenWrt 25.12+:

```sh
. /etc/openwrt_release
wget -O /etc/apk/keys/nieaowei.pem \
  https://nieaowei.github.io/openwrt-packages/public-key.pem
mkdir -p /etc/apk/repositories.d
echo "@nieaowei https://nieaowei.github.io/openwrt-packages/25.12/packages/$DISTRIB_ARCH/packages.adb" \
  > /etc/apk/repositories.d/nieaowei.list
apk update
apk add <package-name>@nieaowei
```

**Important:** Replace `25.12` with the appropriate release series, and only add the source if the corresponding architecture directory exists. APK v3 packages may have dependencies on a specific OpenWrt release, ABI or kernel. A signed package is not automatically compatible with GL.iNet vendor firmware. Avoid broad `apk upgrade` of the entire system.

## Package layout

```text
packages/
  25.12/
    aarch64_cortex-a53/
      example-1.0-r1.apk
    x86_64/
      example-1.0-r1.apk
```

All .apk files placed here are treated as trusted inputs controlled by maintainers. Re-signing makes the published artifacts trust your repository key instead of their original signature. The Actions secret is used only at publish time. The private key is not included in the Pages artifact.

## Maintenance

- To publish a new version, replace/add the APK under the matching series/architecture path and push.
- Only packages checked into this repo are published. Remove old APKs to remove them from the next index.
- Large APKs may run into Git and GitHub Pages limits; for large releases consider external object storage.
- GitHub Pages setup and repository secret configuration must be completed manually in GitHub Settings.
