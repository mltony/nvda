# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2022 NV Access Limited, Łukasz Golonka
# This file may be used under the terms of the GNU General Public License, version 2 or later.
# For more details see: https://www.gnu.org/licenses/gpl-2.0.html

"""AppModule for Notepad++.
Do not rename! The executable file for Notepad++ is named `notepad++` and `+` is not a valid character
in Python's import statements.
This module is mapped to the right binary separately
and the current name makes it possible to expose it from `nvdaBuiltin` for add-on developers.
"""

import ctypes

import appModuleHandler
import NVDAObjects.window.scintilla as ScintillaBase


class CharacterRangeStructLongLong(ctypes.Structure):
	"""By default character ranges in Scintilla are represented by longs.
	However long is not big enough for files over 2 GB,
	therefore in 64-bit builds of Notepad++ 8.3 and later
	these ranges are represented by longlong.
	"""

	_fields_ = [
		("cpMin", ctypes.c_longlong),
		("cpMax", ctypes.c_longlong),
	]


class ScintillaTextInfoNpp83(ScintillaBase.ScintillaTextInfo):
	"""Text info for 64-bit builds of Notepad++ 8.3 and later."""

	class TextRangeStruct(ctypes.Structure):
		_fields_ = [
			("chrg", CharacterRangeStructLongLong),
			("lpstrText", ctypes.c_char_p),
		]


def _isNpp83OrLater(productVersion):
	try:
		appVerMajor, appVerMinor, *appVerTail = productVersion.split(".")
		majorVersion = int(appVerMajor)
		# Notepad++ may report versions in a compact form (e.g. 8.21 for 8.2.1),
		# so with only two components use the first minor digit as the true minor version.
		if appVerTail:
			minorVersion = int(appVerMinor)
		else:
			minorVersion = int(appVerMinor[0])
	except (ValueError, IndexError):
		return False
	return (majorVersion, minorVersion) >= (8, 3)


class NppEdit(ScintillaBase.Scintilla):
	name = None  # The name of the editor is not useful.

	def _get_TextInfo(self):
		if self.appModule.is64BitProcess and _isNpp83OrLater(self.appModule.productVersion):
			return ScintillaTextInfoNpp83
		return super().TextInfo


class AppModule(appModuleHandler.AppModule):
	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		if obj.windowClassName == "Scintilla":
			clsList.insert(0, NppEdit)
