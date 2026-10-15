# Expo / EAS: per-environment iOS and Android builds

## Variants via `app.config.ts`

Each environment installs as a separate app (different bundle id), so dev and prod can coexist
on one device. Drive this with `APP_VARIANT`, set by the EAS build profile:

```ts
import type { ExpoConfig } from "expo/config";

const VARIANT = process.env.APP_VARIANT ?? "development";
const BASE_ID = "com.example.myapp";       // apps.mobile.bundle_id
const BASE_NAME = "MyApp";                 // apps.mobile.name

const suffix = { development: ".dev", preview: ".staging", production: "" }[VARIANT] ?? `.${VARIANT}`;
const label = { development: " (Dev)", preview: " (Staging)", production: "" }[VARIANT] ?? ` (${VARIANT})`;

export default ({ config }: { config: ExpoConfig }): ExpoConfig => ({
  ...config,
  name: BASE_NAME + label,
  ios: { ...config.ios, bundleIdentifier: BASE_ID + suffix },
  android: { ...config.android, package: BASE_ID + suffix },
});
```

If `app.json` exists, keep it and let `app.config.ts` extend it (the `config` argument).

## `eas.json` build profiles

One profile per spec environment, using its `eas_profile`, `eas_environment`, `eas_channel`, `app_variant`:

```json
{
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "environment": "development",
      "channel": "development",
      "env": { "APP_VARIANT": "development" }
    },
    "preview": {
      "distribution": "internal",
      "environment": "preview",
      "channel": "preview",
      "env": { "APP_VARIANT": "preview" }
    },
    "production": {
      "environment": "production",
      "channel": "production",
      "autoIncrement": true,
      "env": { "APP_VARIANT": "production" }
    }
  },
  "submit": { "production": {} }
}
```

## Firebase config per environment

- Using the Firebase JS SDK: store the web config as EAS env vars
  (`EXPO_PUBLIC_FIREBASE_API_KEY`, `..._PROJECT_ID`, …) in each EAS environment:
  `eas env:create --environment preview --name EXPO_PUBLIC_FIREBASE_PROJECT_ID --value myapp-staging --visibility plaintext`.
  Pull them locally with `eas env:pull --environment development`.
- Using `@react-native-firebase`: keep per-variant `google-services.json` /
  `GoogleService-Info.plist` (e.g. `firebase/<env>/`) and select them in `app.config.ts`
  by `APP_VARIANT` via `android.googleServicesFile` / `ios.googleServicesFile`.
  Register one iOS and one Android app per Firebase project with the suffixed bundle id.

## Deploy commands

- Build: `eas build --profile <eas_profile> --platform all`
- OTA update: `eas update --channel <eas_channel>`
- Submit: `eas submit --profile production`
