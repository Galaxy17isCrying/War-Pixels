[app]
title = War Pixels
package.name = warpixels
package.domain = com.galaxylovesrice
source.dir = .
source.include_exts = py,json,txt,mp3,sql
source.exclude_dirs = .git,.venv,__pycache__,tests,tools
source.exclude_patterns = assets/audio/haiya_haiya_better_together.mp3
version = 1.0.0
requirements = python3,pygame
orientation = landscape
fullscreen = 1

android.permissions = INTERNET,ACCESS_NETWORK_STATE
android.ndk = 25b
android.minapi = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
p4a.branch = v2023.09.16
