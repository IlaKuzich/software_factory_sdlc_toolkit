# Self-hosted runners: registration and machine setup

## Scope

Runners on a personal account attach to **one repository**. To share the Mac mini and laptop
across several repos, create a free GitHub organization, move the repos there, and register
org-level runners (`orgs/ORG/actions/runners/...`; `check_runners.py --org ORG`).

## Registration via the GitHub API

Registration tokens are short-lived (1h) and minted via the API:

```sh
gh api -X POST repos/OWNER/REPO/actions/runners/registration-token --jq .token
# org: gh api -X POST orgs/ORG/actions/runners/registration-token --jq .token
```

Download the runner from https://github.com/actions/runner/releases (pick the OS/arch build;
on Apple Silicon use `osx-arm64`), unpack it into `~/actions-runner`, then configure. Default labels
`self-hosted`, OS (`macOS`/`Linux`/`Windows`) and arch are added automatically; `--labels` adds custom ones.

Removal: `gh api -X POST repos/OWNER/REPO/actions/runners/remove-token --jq .token`, then
`./config.sh remove --token <token>`.

## Mac mini (iOS)

```sh
cd ~/actions-runner
./config.sh --url https://github.com/OWNER/REPO --token <TOKEN> \
  --name mac-mini --labels ios --unattended
./svc.sh install && ./svc.sh start
```

- `svc.sh` installs a **LaunchAgent**: it only runs while the user is logged in. Enable automatic
  login (System Settings → Users & Groups) so it survives reboots; iOS signing also needs a user session.
- Disable sleep: `sudo pmset -a sleep 0 disksleep 0`, and enable "Start up automatically after a power failure".
- Toolchain: Xcode (`sudo xcode-select -s /Applications/Xcode.app && sudo xcodebuild -runFirstLaunch`),
  CocoaPods, fastlane (`brew install cocoapods fastlane`), Node 20+.

## Windows laptop (Android): WSL2 (recommended)

`eas build --local` does not run on Windows, so run the runner as a Linux runner inside WSL2:

1. `wsl --install -d Ubuntu`; in `/etc/wsl.conf` set `[boot] systemd=true`, then `wsl --shutdown`.
2. In `%UserProfile%\.wslconfig`: `[wsl2]` `memory=8GB` (or more) and `vmIdleTimeout=-1` so the VM
   isn't stopped while idle.
3. Inside Ubuntu: JDK 17, Node 20+, Android command-line tools (`sdkmanager "platform-tools"
   "platforms;android-35" "build-tools;35.0.0"`), and `ANDROID_HOME` in `~/.profile`.
4. Configure and run as a systemd service:
   ```sh
   cd ~/actions-runner
   ./config.sh --url https://github.com/OWNER/REPO --token <TOKEN> --name win-laptop --labels android --unattended
   echo "ANDROID_HOME=$ANDROID_HOME" >> .env
   sudo ./svc.sh install && sudo ./svc.sh start
   ```
5. Start WSL at Windows logon: Task Scheduler → "At log on" → `wsl.exe -d Ubuntu --exec /bin/true`.
6. Laptop power (on AC): never sleep, lid close → Do nothing. Check with `runner_doctor.ps1 -HostOnly`.

## Windows laptop (Android): native Windows

```powershell
cd C:\actions-runner
.\config.cmd --url https://github.com/OWNER/REPO --token <TOKEN> --name win-laptop --labels android --unattended --runasservice
```

Set `ANDROID_HOME` and `JAVA_HOME` as machine-level environment variables, enable long paths, then
restart the `actions.runner.*` service. Labels become `[self-hosted, Windows, android]`.

### Native Windows Android job

Replace the `android` job's build step in `mobile-build.yml` (keep checkout/pnpm/node/install):

```yaml
    runs-on: [self-hosted, Windows, android]
    defaults:
      run:
        shell: pwsh
    steps:
      # ...checkout, pnpm, node, install...
      - name: prebuild + gradle
        working-directory: ${{ env.APP_DIR }}
        env:
          APP_VARIANT: ${{ vars.APP_VARIANT }}   # per GitHub Environment: development | preview | production
        run: |
          npx expo prebuild --platform android --no-install --clean
          cd android; .\gradlew.bat bundleRelease
      - uses: actions/upload-artifact@v4
        with:
          path: ${{ env.APP_DIR }}/android/app/build/outputs/bundle/release/*.aab
```

Signing must then be configured in Gradle (keystore from a secret) instead of EAS credentials;
EAS env vars aren't loaded, so pass needed `EXPO_PUBLIC_*` values via GitHub Environment variables.
