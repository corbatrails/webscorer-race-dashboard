# Changelog

## 1.0.0 (2026-08-09)


### Features

* add config loading and WebScorer API client ([33d69f1](https://github.com/corbatrails/webscorer-race-dashboard/commit/33d69f155c67a719301f81f945a573d97394f376))
* add configurable RESULTS_PER_PAGE (0 = auto-fit to viewport) ([73e3acc](https://github.com/corbatrails/webscorer-race-dashboard/commit/73e3accdce358b4951370e7291be5c058e71f2e1))
* add dashboard frontend with page rotation ([4834a09](https://github.com/corbatrails/webscorer-race-dashboard/commit/4834a099b2bc745adeb53e1a002fa68985d59e25))
* add data processing layer with process_race_data and build_pages ([1b38bb2](https://github.com/corbatrails/webscorer-race-dashboard/commit/1b38bb2282d78fed840f9c8915bf99c2bc43fecb))
* add Flask server with background polling and race selection ([45a29e0](https://github.com/corbatrails/webscorer-race-dashboard/commit/45a29e0a0bd8e1a73f2795d90856fd1e0d3041a2))
* add SHOW_SUMMARY and SHOW_CATEGORIES toggles ([ecb3a39](https://github.com/corbatrails/webscorer-race-dashboard/commit/ecb3a3912f3c8cf27f08bc8c663a5d1315adb629))
* add start script and README ([4bf5183](https://github.com/corbatrails/webscorer-race-dashboard/commit/4bf5183423eb6178c52d3a942184857f1d280dcc))
* include race name and date in startup log ([05159b5](https://github.com/corbatrails/webscorer-race-dashboard/commit/05159b5eb92654ab6acc33483f7ffc2a4620127e))
* log startup configuration ([9556855](https://github.com/corbatrails/webscorer-race-dashboard/commit/9556855975ba63fb3a0b62c5ae10b99216e958d3))
* rename start-app.sh to start.sh, add start.ps1 for Windows ([545434f](https://github.com/corbatrails/webscorer-race-dashboard/commit/545434fdc736dde41b79e43a83996c507cedbca7))
* responsive page splitting based on viewport, consistent row/column sizes ([ed24545](https://github.com/corbatrails/webscorer-race-dashboard/commit/ed24545d5469702601127e11b7c07bce895c018f))
* show gender in category page header ([88d2851](https://github.com/corbatrails/webscorer-race-dashboard/commit/88d28513317003a499bb65aab32b3e65d9bc38af))


### Bug Fixes

* increase bottom padding further ([2b8ffc2](https://github.com/corbatrails/webscorer-race-dashboard/commit/2b8ffc23f4cb4ee18be3f75ad1cddc4888e6ea0d))
* increase bottom padding to prevent progress dots overlapping results ([2918988](https://github.com/corbatrails/webscorer-race-dashboard/commit/291898890f64329d70fe37b671331f140e062668))
* move category page number next to title ([7405f91](https://github.com/corbatrails/webscorer-race-dashboard/commit/7405f91474a8315d29f2ef0ac156c88d77e15366))
* move last-updated to summary header ([ff5b47d](https://github.com/corbatrails/webscorer-race-dashboard/commit/ff5b47df58ff0cf8807c8cb2130bd070d8fbae47))
* prevent table rows from stretching to fill page ([60782cf](https://github.com/corbatrails/webscorer-race-dashboard/commit/60782cf34eb9583b1ad55192b3d9101dac213e11))
* progress dots visibility and rotation timer update ([1a8ecf0](https://github.com/corbatrails/webscorer-race-dashboard/commit/1a8ecf0b8ed9bddcc3fe4a7d3ec50c458e5aa2d4))
* separate race info onto individual lines in startup log ([54b9653](https://github.com/corbatrails/webscorer-race-dashboard/commit/54b9653dbdc8a7f86368773925456d9192e733d3))
* set custom User-Agent to avoid WAF 403, improve race selection error handling ([3eec9dc](https://github.com/corbatrails/webscorer-race-dashboard/commit/3eec9dc912d9f106a997abf08f62232e7e259867))
* strip API credentials from error messages shown on frontend ([4069648](https://github.com/corbatrails/webscorer-race-dashboard/commit/40696482a3a9290b552639f5a99b49e6664ff68d))
