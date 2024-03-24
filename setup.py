"""
This is a setup.py script generated by py2applet

Usage:
    python setup.py py2app
"""

from setuptools import setup

APP_NAME='glinet menubar'
APP = ['main.py']
DATA_FILES = ['glinet-fav.png']
OPTIONS = {
    'iconfile':'./glinet.icns',
    'argv_emulation': False,
    'plist': {
        'LSUIElement': True,
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleGetInfoString': "glinet menubar",
        'CFBundleIdentifier': "net.jinpark.glinet-menubar",
        'CFBundleVersion': "0.1.3",
        'CFBundleShortVersionString': "0.1.3",
        'NSHumanReadableCopyright': u"Copyright © 2024, Jin Park, All Rights Reserved"
    },
    'packages': ['rumps'],
    'includes': ['rumps', 'chardet', 'ipython', 'passlib', 'requests', 'tabulate'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    requires=['py2app', 'rumps'],
)
