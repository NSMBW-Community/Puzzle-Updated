Puzzle Tileset Editor ("Puzzle-Updated" fork)
=============================================

Advanced tileset editor for New Super Mario Bros. Wii, created by
Tempus using Python, PyQt and Wii.py.

The "Puzzle-Updated" fork is a modern evolution of the original Puzzle
codebase, focusing on stability and future-proofing.

Bugfixes are a priority. Minor new features are allowed, so long as most people
are in favor of them. Major new features that aren't really necessary will
generally be declined. Support for newly discovered tileset options/settings
will always be added when possible, though I may wait until they've been
thoroughly tested first.

If you want a NSMBW tileset editor with more features (possibly at the expense
of some stability and simplicity), consider
[Puzzle Next](https://github.com/NSMBW-Community/Puzzle-Next), another Puzzle
fork with somewhat different project goals.


Requirements
============

If you are using the source release:

- A recent release of Python 3 — https://www.python.org
- Any of the following:
    - PyQt 6.1.1 (or newer) **(RECOMMENDED)** — `pip install PyQt6`
    - PyQt 5.11 (or newer) (use if PyQt6 isn't available for your system) — `pip install PyQt5`
    - Qt for Python 5.12 (or newer) (NOT RECOMMENDED) — `pip install PySide2`
- NSMBLib 0.5 (or newer) — `pip install nsmblib` (optional)

If you have a prebuilt/frozen release (for Windows, macOS or Ubuntu),
you don't need to install anything — all the required libraries are included.


macOS Troubleshooting
=====================

If you get the error "Puzzle Tileset Editor is damaged and can't be opened.",
it's because the release builds are unsigned. To fix it, launch a Terminal
window and run

    sudo xattr -rd com.apple.quarantine "/path/to/Puzzle Tileset Editor.app"

...with the example path above replaced with the actual path to the app. This
will override the application signature requirement, which should allow you to
launch the app.


Puzzle Team
===========

Developers
----------
- Tempus — Original developer
- RoadrunnerWMC — "Puzzle-Updated" Fork


Libraries/Resources
===================

- Qt — The Qt Company (https://www.qt.io)
- Qt for Python — The Qt Company (https://www.qt.io)
- PyQt — Riverbank Computing (https://riverbankcomputing.com/software/pyqt/intro)
- Wii.py — megazig, Xuzz, The Lemon Man, Matt_P, SquidMan, Omega (https://github.com/grp/Wii.py)


Licensing
=========

Puzzle is released under the GNU General Public License v2.
See the license file in the distribution for information.


Changelog
=========

Puzzle-Updated 2022.12.05.0:
----------------------------
- **IMPORTANT:** This is the first release that truly addresses the "black
  borders" bug, in which faint black outlines were visible around tiles. This
  occurred because RGB values for fully transparent pixels were being set to
  zero, causing issues during texture blending. Puzzle now accurately preserves
  transparent pixel colors in all situations.
    - Since PNG images may have missing or nonsensical colors for transparent
      pixels depending on the tools used, a new dialog has been added, shown
      when importing an image, to offer optional automatic tile-edge color
      adjustment. This works well in some, but not all, cases.
- Added support for PyQt6. PyQt5 is also still supported.
- The File menu now shows the versions of Python, PyQt, Qt, and nsmblib
  currently in use.
- The "Horiz. Center Left" and "Horiz. Center Right" pipe collision types have
  been renamed to "Horiz. Center Top" and "Horiz. Center Bottom" respectively,
  since the original names didn't really make sense.
- Puzzle now keeps track of the most recent Open / Save and Import / Export
  file paths across sessions, to hopefully eliminate redundant directory
  navigation.
- Other various bugfixes.


Puzzle-Updated 2021.03.01.0:
----------------------------
- Fixed (hopefully — it works for everyone I've asked, at least) a bug causing
  the tileset image view to wrap incorrectly (15x18 tiles instead of 16x16)
  with certain OS monitor/display settings.
- Ported the recent CI infrastructure changes from Reggie Updated, so releases
  will now include Windows-7-compatible builds.
- Small performance enhancements for tileset saving.


Puzzle-Updated 2021.01.10.0:
----------------------------
- **IMPORTANT:** Fixed a large bug in tileset encoding. Please open and resave
  any tilesets you've saved with previous versions of Puzzle-Updated (since
  late 2018), or else they may look incorrect in-game! (Broken tilesets look
  fine in Reggie and Puzzle.) (Thanks to G4L for reporting.)
- Each release will now include 32-bit Windows builds, in addition to the
  64-bit ones.
- Fixed a bug that could prevent Puzzle from running properly in some
  situations (such as when launching from the Start menu on Windows).


Puzzle-Updated 2020.10.26.0:
----------------------------
- Release builds for macOS now support system-wide dark mode.
    - This unfortunately required dropping support in the release builds for
      macOS older than 10.13 (High Sierra). You can still run Puzzle-Updated
      from source code on older macOS versions, though.
- Release builds now use Python 3.9.
- Implemented a new technique to shrink download sizes. Windows builds are now
  ~38% smaller compared to the previous release, and Ubuntu builds are ~12%
  smaller. macOS is unfortunately not affected.
    - I've tested this as best I can, but there is a small chance this change
      may prevent Puzzle from running for some users. Please open an issue if
      the previous release works for you and this one doesn't.


Puzzle-Updated 2020.05.29.0:
----------------------------
- Fixed a bug that could cause crashes.


Puzzle-Updated 2020.05.18.0:
----------------------------
- The incomplete "Add Item..." feature (in the right-click menu for tiles in
  objects) has been finished, and renamed to "Set Item...".


Puzzle-Updated 2020.05.17.0:
----------------------------
- Puzzle is now compatible with Python 3, PyQt5, and Qt for Python (PySide2).
- NSMBLib has been removed from this repository — you can find it at
  https://github.com/RoadrunnerWMC/NSMBLib-Updated
- A full changelog was unfortunately not recorded for this release.


0.6: (June 6th, 2010)
---------------------
- First public release.
