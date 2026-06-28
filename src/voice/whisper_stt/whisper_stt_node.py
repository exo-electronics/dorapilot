#!/usr/bin/env python3
"""Whisper STT via Hailo-15H HEF — audio → mel → HEF inference → text.

Hailo-15H (20 TOPS, M.2 PCIe) provides the inference backend via hailort Python API.
Model: whisper_tiny_10s_encoder.hef + decoder (CPU greedy)

Inputs:
  wake_event  — String (from wake_word) — starts session
  audio_pcm   — raw PCM bytes (from mic)
  vad_active  — Bool (from vad) — False triggers transcription

Outputs:
  stt_text    — String (final transcription)
  stt_active  — Bool (session open/closed)
"""
import os
import time
from dora import Node
import numpy as np

from drp_msgs.std_msgs import String, Bool
from drp_msgs.utils import to_arrow, from_arrow


class WhisperSttNode:
    MODEL_HEF = os.environ.get("WHISPER_HEF", "/data/models/whisper_tiny_10s_encoder.hef")
    SAMPLE_RATE = 16000
    MAX_SESSION_SEC = 10.0

    def __init__(self):
        self.node = Node()
        self._active = False
        self._session_start = 0.0
        self._audio_buffer: list[float] = []
        self._hailo_infer = self._init_hailo()

    def _init_hailo(self):
        try:
            from hailo_platform import HEF, VDevice, HailoStreamInterface, InferVStreams, ConfigureParams
            params = VDevice.create_params()
            vdevice = VDevice(params)
            hef = HEF(self.MODEL_HEF)
            configure_params = ConfigureParams.create_from_hef(hef, interface=HailoStreamInterface.PCIe)
            network_groups = vdevice.configure(hef, configure_params)
            return {"vdevice": vdevice, "network_groups": network_groups, "hef": hef}
        except Exception:
            return None  # runs in stub mode without Hailo hardware

    def run(self):
        for event in self.node:
            if event["type"] != "INPUT":
                if event["type"] == "STOP":
                    break
                continue

            eid = event["id"]
            if eid == "wake_event" and not self._active:
                self._start_session()
            elif eid == "audio_pcm" and self._active:
                self._buffer_audio(event)
            elif eid == "vad_active" and self._active:
                vad = from_arrow(event["value"], Bool)
                if not vad.data:
                    self._finish_session()

    def _start_session(self):
        self._active = True
        self._session_start = time.time()
        self._audio_buffer.clear()
        self.node.send_output("stt_active", to_arrow(Bool(data=True)))

    def _buffer_audio(self, event):
        pcm = event["value"].to_numpy().view(np.int16).astype(np.float32) / 32768.0
        self._audio_buffer.extend(pcm.tolist())
        if time.time() - self._session_start > self.MAX_SESSION_SEC:
            self._finish_session()

    def _finish_session(self):
        self._active = False
        self.node.send_output("stt_active", to_arrow(Bool(data=False)))

        audio = np.array(self._audio_buffer, dtype=np.float32)
        if len(audio) < self.SAMPLE_RATE * 0.2:
            return

        text = self._transcribe(audio)
        if text:
            self.node.send_output("stt_text", to_arrow(String(data=text)))

    def _transcribe(self, audio: np.ndarray) -> str:
        mel = self._compute_mel(audio)
        logits = self._hailo_run(mel) if self._hailo_infer else None
        if logits is None:
            return ""
        return self._greedy_decode(logits)

    def _compute_mel(self, audio: np.ndarray) -> np.ndarray:
        target = self.SAMPLE_RATE * 10
        if len(audio) < target:
            audio = np.pad(audio, (0, target - len(audio)))
        else:
            audio = audio[:target]
        n_fft, hop, n_mels, n_frames = 400, 160, 80, 1000
        required = (n_frames - 1) * hop + n_fft
        if len(audio) < required:
            audio = np.pad(audio, (0, required - len(audio)))
        frames = np.lib.stride_tricks.sliding_window_view(audio, n_fft)[::hop][:n_frames]
        frames = frames * np.hanning(n_fft)
        stft = np.abs(np.fft.rfft(frames, axis=1))
        fb = np.linspace(0, stft.shape[1], n_mels + 2)
        fb = np.diff(np.floor(fb)).astype(bool)[:-1].astype(float)
        mel = np.dot(fb[:, np.newaxis] * np.ones((1, stft.shape[1])) / (fb.sum() + 1e-8), stft.T)
        return np.log(np.clip(mel, 1e-10, None)).astype(np.float32)

    def _hailo_run(self, mel: np.ndarray):
        try:
            from hailo_platform import InferVStreams, ConfigureParams
            ng = self._hailo_infer["network_groups"][0]
            with ng.activate():
                with InferVStreams(ng, {}) as pipeline:
                    result = pipeline.infer({"input": mel[np.newaxis]})
                    return next(iter(result.values()))
        except Exception:
            return None

    def _greedy_decode(self, logits: np.ndarray) -> str:
        # TODO: integrate Whisper tokenizer (tiktoken or whisper.tokenizer)
        return ""


if __name__ == "__main__":
    WhisperSttNode().run()
