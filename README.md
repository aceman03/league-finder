# League Finder

Android app for searching and filtering bowling leagues by location, day,
time, format, skill level and more.

The app contains no league data. On first launch it asks for a GitHub token
and downloads the dataset from a private repo you control (default
`aceman03/league-data`, file `data/leagues.json`). Data and settings stay on
the device; the app re-checks for new data each time it opens and keeps
working offline with the last copy.

## Install

**With the token built in (recommended):** build the APK from the private
data repo: `aceman03/league-data` > Actions > **Build APK** > Run
workflow, then download the `league-finder-apk` artifact. Installs from that
build load data without asking for a token. See that repo's README for the
one-time secret setup.

**Without a built-in token:** this repo's Actions > **Build APK** artifact
asks for a token on first launch. Create a fine-grained token at GitHub >
Settings > Developer settings > Personal access tokens > Fine-grained
tokens: **Only select repositories** > your data repo, **Repository
permissions > Contents: Read-only**. Paste it into the app.

Either way: unzip the artifact, copy `app-debug.apk` to your phone and open
it. Android will ask you to allow installing from that source.

A token entered in the app overrides the built-in one, so an expired
built-in token can be replaced without reinstalling.

## Develop

    cd app
    npm install
    npm run serve          # web UI at http://localhost:8080
    npx cap sync android   # copy www/ into the Android project

The UI is plain HTML/CSS/JS in `app/www/`; `app/android/` is the Capacitor
Android project. Pushes that touch `app/` build a new APK in CI.
