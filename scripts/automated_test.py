import os
import sys


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, repo_root)

    from launchpad_mapper import LaunchpadMapper

    mapper = LaunchpadMapper()
    backends = mapper.get_midi_backends()
    assert isinstance(backends, list) and backends, "No MIDI backends discovered"

    invalid = mapper.set_midi_backend("mido.backends.invalid")
    assert invalid.get("success") is False, "Invalid backend should fail"

    from launchpad_mapper import PadMapping

    mapper.profile.add_mapping(
        PadMapping(
            note=60,
            key_combo="space",
            color="green",
            label="Test",
            enabled=True,
        )
    )
    mapper.execute_key_combo = lambda _combo: None
    result = mapper.emulate_pad_press(60)
    assert result.get("success") is True, "Emulated pad press should succeed"

    print("Automated checks passed.")


if __name__ == "__main__":
    main()
