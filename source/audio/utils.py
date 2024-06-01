# A part of NonVisual Desktop Access (NVDA)
# Copyright (C) 2024 NV Access Limited
# This file is covered by the GNU General Public License.
# See the file COPYING for more details.

from logHandler import log
from pycaw.api.audiopolicy import IAudioSessionManager2
from pycaw.callbacks import AudioSessionNotification, AudioSessionEvents
from pycaw.utils import AudioSession, AudioUtilities
from dataclasses import dataclass, field
from comtypes import COMError
from threading import Lock
from pycaw.api.audiopolicy import IAudioSessionControl2
import weakref


_audioSessionManager: IAudioSessionManager2 | None = None


def initialize() -> None:
	global _audioSessionManager
	try:
		_audioSessionManager = AudioUtilities.GetAudioSessionManager()
	except COMError:
		log.exception("Could not initialize audio session manager")
		return


def terminate():
	global _audioSessionManager
	_audioSessionManager = None


class AudioSessionEventsListener(AudioSessionEvents):
	callback: "weakref.ReferenceType[AudioSessionCallback]"
	pid: int
	audioSession: AudioSession

	def __init__(self, callback: "AudioSessionCallback", pid: int, audioSession: AudioSession):
		self.callback = weakref.ref(callback)
		self.pid = pid
		self.audioSession = audioSession

	def on_state_changed(self, new_state: str, new_state_id: int):
		if new_state == "Expired":
			self.onSessionTerminated()

	def onSessionTerminated(self):
		self.callback().onSessionTerminated(self.audioSession)
		self.unregister()
		with self.callback()._lock:
			self.callback()._audioSessionEventListeners.remove(self)

	def unregister(self):
		try:
			self.audioSession.unregister_notification()
		except Exception:
			log.exception(f"Cannot unregister audio session for process {self.pid}")


class AudioSessionNotificationListener(AudioSessionNotification):
	callback: "weakref.ReferenceType[AudioSessionCallback]"

	def __init__(self, callback: "AudioSessionCallback"):
		self.callback = weakref.ref(callback)

	def on_session_created(self, new_session: AudioSession):
		pid = new_session.ProcessId
		audioSessionEventsListener = AudioSessionEventsListener(self.callback(), pid, new_session)
		new_session.register_notification(audioSessionEventsListener)
		with self.callback()._lock:
			self.callback()._audioSessionEventListeners.add(audioSessionEventsListener)
		self.callback().onSessionUpdate(new_session)


class DummyAudioSessionCallback:
	def register(self, applyToFuture: bool = True):
		pass

	def unregister(self, runTerminators: bool = True):
		pass


@dataclass(unsafe_hash=True)
class AudioSessionCallback(DummyAudioSessionCallback):
	"""
	This is an abstract class that allows implementing custom logic, that will be applied to all WASAPI
	audio sessions. Consumers are expected to implement functions:
	* def onSessionUpdate(self, session: AudioSession):
		It will be called once for every existing audio session and also will be scheduled to be called
		for every new audio session.
	* def onSessionTerminated(self, session: AudioSession):
		It will be called when an audio session is terminated or when unregister() is called, which
		typically happens when NVDA quits.
	"""
	_lock: Lock = Lock()
	_audioSessionNotification: AudioSessionNotification | None = None
	_audioSessionEventListeners: set[AudioSessionEventsListener] = field(default_factory=set)

	def onSessionUpdate(self, session: AudioSession) -> None:
		pass

	def onSessionTerminated(self, session: AudioSession) -> None:
		pass

	def register(self, applyToFuture: bool = True):
		_applyToAllAudioSessions(self, applyToFuture)

	def unregister(self, runTerminators: bool = True):
		if self._audioSessionNotification is not None:
			_audioSessionManager.UnregisterSessionNotification(self._audioSessionNotification)
		with self._lock:
			listenersCopy = list(self._audioSessionEventListeners)
		for audioSessionEventListener in listenersCopy:
			if runTerminators:
				audioSessionEventListener.on_state_changed("Expired", 0)
			else:
				audioSessionEventListener.audioSession.unregister_notification()


def _applyToAllAudioSessions(
		callback: AudioSessionCallback,
		applyToFuture: bool = True,
) -> None:
	"""
	Executes provided callback function on all active audio sessions.
	Additionally, if applyToFuture is True, then it will register a notification with audio session manager,
	which will execute the same callback for all future sessions as they are created.
	"""
	listener = AudioSessionNotificationListener(callback)
	if applyToFuture:
		_audioSessionManager.RegisterSessionNotification(listener)
		callback._audioSessionNotification = listener
	sessionEnumerator = _audioSessionManager.GetSessionEnumerator()
	count = sessionEnumerator.GetCount()
	for i in range(count):
		ctl = sessionEnumerator.GetSession(i)
		if ctl is None:
			continue
		ctl2 = ctl.QueryInterface(IAudioSessionControl2)
		if ctl2 is not None:
			audioSession = AudioSession(ctl2)
			listener.on_session_created(audioSession)
