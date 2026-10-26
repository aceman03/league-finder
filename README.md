# League Finder

Android app for searching and filtering bowling leagues by location, day,
time, format, skill level and more.

The app contains no league data. On first launch it asks for a GitHub token
and downloads the dataset from a private repo you control (default
`aceman03/league-data`, file `data/leagues.json`). Data and settings stay on
the device; the app re-checks for new data each time it opens and keeps
working offline with the last copy.

## Install

Install the APK from a release in the private data repo
(`aceman03/league-data` > Releases > `League-Finder.apk`). Those builds have
the data token built in, so they open straight to the leagues, and they're
signed with the key later updates use. To make a new one: `league-data` >
Actions > **Build APK** > Run workflow (see that repo's README for the
one-time secret setup).

This repo's Actions only check that the app compiles; they don't produce an
installable APK.

A token entered in the app overrides the built-in one, so an expired
built-in token can be replaced without reinstalling. The settings screen
shows whether the installed build has a token built in.

## Updates

The app checks for a newer release on launch (at most every 6 hours), every
30 minutes while open, and from **Settings > Check for updates**. Releases
live in the private data repo (`aceman03/league-data`), since those APKs
carry the data token. When one is newer, a banner offers **Download** and
**What's new**. Download fetches the APK inside the app with the data token
(no browser or GitHub sign-in) and opens Android's installer; the first time,
Android asks to allow installing apps from League Finder.

To ship a version:

1. Bump `"version"` in `app/package.json`. It flows into `www/version.js`
   (`npm run version`, also run by `npm run sync`) and the Android
   `versionName`/`versionCode`.
2. Push, then run **Build APK** in `aceman03/league-data`. It publishes
   release `vX.Y.Z` with `League-Finder.apk` attached.

## Develop

    cd app
    npm install
    npm run serve          # web UI at http://localhost:8080
    npx cap sync android   # copy www/ into the Android project

The UI is plain HTML/CSS/JS in `app/www/`; `app/android/` is the Capacitor
Android project. Pushes that touch `app/` build a new APK in CI.
