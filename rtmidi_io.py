"""
Drop-in, no-mido MIDI wrapper using python-rtmidi.

Install:
  pip install python-rtmidi

What you get:
  - list_input_ports(), list_output_ports()
  - open(input_name=..., output_name=..., on_message=...)
  - close()
  - send(message_bytes) for MIDI messages (including SysEx)
  - safe reconnect and port auto-pick helpers

Notes:
  - python-rtmidi expects messages as a list/tuple of ints (0-255).
  - SysEx must include 0xF0 ... 0xF7.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence, Tuple

import rtmidi


MidiCallback = Callable[[List[int], float], None]


@dataclass
class OpenedPorts:
    input_port_name: str
    output_port_name: str
    input_port_index: int
    output_port_index: int


class RtMidiIO:
    """
    Minimal replacement for mido usage patterns:
      - enumerate ports
      - open input and output
      - receive messages via callback
      - send messages (note, cc, sysex)

    This class does not interpret MIDI, it just moves bytes.
    """

    def __init__(self) -> None:
        self._midi_in: Optional[rtmidi.MidiIn] = None
        self._midi_out: Optional[rtmidi.MidiOut] = None
        self._opened: Optional[OpenedPorts] = None
        self._on_message: Optional[MidiCallback] = None

    # -------- Port enumeration --------

    def list_input_ports(self) -> List[str]:
        mi = rtmidi.MidiIn()
        try:
            return list(mi.get_ports())
        finally:
            del mi

    def list_output_ports(self) -> List[str]:
        mo = rtmidi.MidiOut()
        try:
            return list(mo.get_ports())
        finally:
            del mo

    def find_port_index(
        self,
        ports: Sequence[str],
        *,
        exact_name: Optional[str] = None,
        contains: Optional[Sequence[str]] = None,
        exclude_contains: Optional[Sequence[str]] = None,
        prefer_contains: Optional[Sequence[str]] = None,
    ) -> int:
        """
        Returns the best port index using simple scoring.

        exact_name: if provided, must match exactly (case-sensitive), else error.
        contains: required substrings (case-insensitive), any match qualifies.
        exclude_contains: substrings to reject (case-insensitive).
        prefer_contains: substrings to add score (case-insensitive).
        """
        if exact_name is not None:
            for i, p in enumerate(ports):
                if p == exact_name:
                    return i
            raise RuntimeError(f'Port not found: "{exact_name}"')

        contains_l = [c.lower() for c in (contains or [])]
        exclude_l = [c.lower() for c in (exclude_contains or [])]
        prefer_l = [c.lower() for c in (prefer_contains or [])]

        best_i = -1
        best_score = -10**9

        for i, p in enumerate(ports):
            pl = p.lower()

            # reject
            if any(x in pl for x in exclude_l):
                continue

            # qualify
            if contains_l:
                if not any(x in pl for x in contains_l):
                    continue

            score = 0
            # prefer matches
            for x in prefer_l:
                if x in pl:
                    score += 10

            # slight bias toward earlier ports
            score -= i

            if score > best_score:
                best_score = score
                best_i = i

        if best_i < 0:
            raise RuntimeError("No matching MIDI port found.")
        return best_i

    # -------- Open / Close --------

    def open(
        self,
        *,
        input_name: Optional[str] = None,
        output_name: Optional[str] = None,
        on_message: Optional[MidiCallback] = None,
        input_index: Optional[int] = None,
        output_index: Optional[int] = None,
        match_keywords: Optional[Sequence[str]] = None,
        exclude_keywords: Optional[Sequence[str]] = None,
        prefer_keywords: Optional[Sequence[str]] = None,
        ignore_daw_ports: bool = True,
    ) -> OpenedPorts:
        """
        Open MIDI input and output ports.

        Recommended for Launchpad MK2 on Windows:
          match_keywords=["launchpad", "novation", "mk2"]
          prefer_keywords=["standalone", "midi"]
          exclude_keywords=["daw"]
        """
        self.close()

        self._on_message = on_message

        in_ports = self.list_input_ports()
        out_ports = self.list_output_ports()

        if not in_ports:
            raise RuntimeError("No MIDI input ports detected.")
        if not out_ports:
            raise RuntimeError("No MIDI output ports detected.")

        if ignore_daw_ports:
            daw_excl = ["daw"]
        else:
            daw_excl = []

        # Decide input index
        if input_index is not None:
            in_idx = input_index
        elif input_name is not None:
            in_idx = self.find_port_index(in_ports, exact_name=input_name)
        else:
            in_idx = self.find_port_index(
                in_ports,
                contains=match_keywords,
                exclude_contains=list(exclude_keywords or []) + daw_excl,
                prefer_contains=prefer_keywords,
            )

        # Decide output index
        if output_index is not None:
            out_idx = output_index
        elif output_name is not None:
            out_idx = self.find_port_index(out_ports, exact_name=output_name)
        else:
            out_idx = self.find_port_index(
                out_ports,
                contains=match_keywords,
                exclude_contains=list(exclude_keywords or []) + daw_excl,
                prefer_contains=prefer_keywords,
            )

        midi_in = rtmidi.MidiIn()
        midi_out = rtmidi.MidiOut()

        midi_in.ignore_types(sysex=False, timing=False, sensing=False)

        # Open ports
        try:
            midi_in.open_port(in_idx)
        except Exception as e:
            raise RuntimeError(
                f'Failed to open MIDI input "{in_ports[in_idx]}". '
                f'Another app may be using it. Details: {e}'
            )

        try:
            midi_out.open_port(out_idx)
        except Exception as e:
            try:
                midi_in.close_port()
            except Exception:
                pass
            raise RuntimeError(
                f'Failed to open MIDI output "{out_ports[out_idx]}". '
                f'Another app may be using it. Details: {e}'
            )

        self._midi_in = midi_in
        self._midi_out = midi_out

        self._opened = OpenedPorts(
            input_port_name=in_ports[in_idx],
            output_port_name=out_ports[out_idx],
            input_port_index=in_idx,
            output_port_index=out_idx,
        )

        # Attach callback
        if self._on_message is not None:
            self._midi_in.set_callback(self._rtmidi_callback)

        return self._opened

    def close(self) -> None:
        if self._midi_in is not None:
            try:
                self._midi_in.set_callback(None)
            except Exception:
                pass
            try:
                self._midi_in.close_port()
            except Exception:
                pass
            self._midi_in = None

        if self._midi_out is not None:
            try:
                self._midi_out.close_port()
            except Exception:
                pass
            self._midi_out = None

        self._opened = None
        self._on_message = None

    @property
    def is_open(self) -> bool:
        return (
            self._midi_in is not None
            and self._midi_out is not None
            and self._opened is not None
        )

    @property
    def opened_ports(self) -> Optional[OpenedPorts]:
        return self._opened

    # -------- Send / Receive --------

    def _rtmidi_callback(self, event: Tuple[List[int], float], _data=None) -> None:
        msg, delta_seconds = event
        cb = self._on_message
        if cb is None:
            return
        try:
            cb(list(msg), float(delta_seconds))
        except Exception:
            # Do not crash the MIDI thread
            return

    def send(self, message: Sequence[int]) -> None:
        if self._midi_out is None:
            raise RuntimeError("MIDI output is not open.")
        self._midi_out.send_message(list(message))

    # Convenience helpers
    def note_on(self, note: int, velocity: int = 127, channel: int = 0) -> None:
        status = 0x90 | (channel & 0x0F)
        self.send([status, note & 0x7F, velocity & 0x7F])

    def note_off(self, note: int, velocity: int = 0, channel: int = 0) -> None:
        status = 0x80 | (channel & 0x0F)
        self.send([status, note & 0x7F, velocity & 0x7F])

    def cc(self, controller: int, value: int, channel: int = 0) -> None:
        status = 0xB0 | (channel & 0x0F)
        self.send([status, controller & 0x7F, value & 0x7F])

    def sysex(self, data: Sequence[int]) -> None:
        d = list(data)
        if not d or d[0] != 0xF0:
            d = [0xF0] + d
        if d[-1] != 0xF7:
            d = d + [0xF7]
        self.send(d)

    # -------- Simple reconnect helper --------

    def reconnect(
        self,
        *,
        input_name: Optional[str] = None,
        output_name: Optional[str] = None,
        on_message: Optional[MidiCallback] = None,
        retries: int = 3,
        retry_delay: float = 0.5,
        match_keywords: Optional[Sequence[str]] = None,
        exclude_keywords: Optional[Sequence[str]] = None,
        prefer_keywords: Optional[Sequence[str]] = None,
        ignore_daw_ports: bool = True,
    ) -> OpenedPorts:
        last_err: Optional[Exception] = None
        for _ in range(max(1, retries)):
            try:
                return self.open(
                    input_name=input_name,
                    output_name=output_name,
                    on_message=on_message,
                    match_keywords=match_keywords,
                    exclude_keywords=exclude_keywords,
                    prefer_keywords=prefer_keywords,
                    ignore_daw_ports=ignore_daw_ports,
                )
            except Exception as e:
                last_err = e
                time.sleep(max(0.0, float(retry_delay)))
        raise RuntimeError(
            f"Failed to reconnect after {retries} tries. Last error: {last_err}"
        )


# ---------------- Integration patterns ----------------
#
# 1) Replace mido.get_input_names()/get_output_names()
#    io = RtMidiIO()
#    inputs = io.list_input_ports()
#    outputs = io.list_output_ports()
#
# 2) Replace mido.open_input/open_output and output.send(...)
#    def on_msg(msg, dt):
#        print("IN", msg, dt)
#
#    io.open(
#        input_name="3- Launchpad MK2 0",
#        output_name="3- Launchpad MK2 1",
#        on_message=on_msg,
#    )
#    io.send([0x90, 11, 127])  # note on
#
# 3) Auto-pick Launchpad ports
#    io.open(
#        match_keywords=["launchpad", "novation", "mk2"],
#        prefer_keywords=["standalone", "midi"],
#        exclude_keywords=["daw"],
#        on_message=on_msg,
#    )
