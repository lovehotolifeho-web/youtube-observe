[app]

title = YouTube Observe
package.name = youtube_observe
package.domain = org.ytobserve

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json

version = 1.0.0

requirements = python3,kivy,requests,pillow,plyer

orientation = portrait
fullscreen = 0

[app:android]

permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,ACCESS_NETWORK_STATE,POST_NOTIFICATIONS

android.api = 31
android.minapi = 21
android.ndk = 25b
android.accept_sdk_license = True
android.bootstrap = sdl2
android.archs = arm64-v8a
android.gradle_dependencies =

[buildozer]

log_level = 2
warn_on_root = 1
