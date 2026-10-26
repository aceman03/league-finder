# League Finder

Android app for searching and filtering bowling leagues by location, day,
time, format, skill level and more.

The app contains no league data. On first launch it asks for a GitHub token
and downloads the dataset from a private repo you control (default
`aceman03/league-data`, file `data/leagues.json`). Data and settings stay on
the device; the app re-checks for new data each time it opens and keeps
working offline with the last copy.

## Install

1. Open the **Actions** tab → **Build APK** → latest successful run, and
   download the `league-finder-apk` artifact (a zip containing
   `app-debug.apk`).
2. Copy the APK to your phone and open it. Android will ask you to allow
   installing from that source.
3. Create a fine-grained token at GitHub → Settings → Developer settings →
   Personal access tokens → Fine-grained tokens: **Only select
   repositories** → your data repo, **Repository permissions → Contents:
   Read-only**. Paste it into the app.

## Develop

    cd app
    npm install
    npm run serve          # web UI at http://localhost:8080
    npx cap sync android   # copy www/ into the Android project

The UI is plain HTML/CSS/JS in `app/www/`; `app/android/` is the Capacitor
Android project. Pushes that touch `app/` build a new APK in CI.
