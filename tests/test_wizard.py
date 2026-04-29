from meeting_scribe.wizard import _parse_mic_sources, _suggest_whisper


PACTL_SAMPLE = (
    "62\talsa_output.usb-C-Media.analog-stereo.monitor\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
    "63\talsa_input.usb-C-Media.analog-stereo\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
    "65\talsa_input.usb-ASUS_Xonar_U7.analog-stereo\tPipeWire\ts24le 2ch 48000Hz\tSUSPENDED\n"
    "66\talsa_output.pci-0000_00_1f.3.analog-stereo.monitor\tPipeWire\ts32le 2ch 48000Hz\tRUNNING\n"
    "67\talsa_input.pci-0000_00_1f.3.analog-stereo\tPipeWire\ts32le 2ch 48000Hz\tSUSPENDED\n"
)


def test_parse_mic_sources_drops_monitor_sources():
    sources = _parse_mic_sources(PACTL_SAMPLE)
    assert all(".monitor" not in s for s in sources)


def test_parse_mic_sources_keeps_real_inputs():
    sources = _parse_mic_sources(PACTL_SAMPLE)
    assert "alsa_input.usb-C-Media.analog-stereo" in sources
    assert "alsa_input.usb-ASUS_Xonar_U7.analog-stereo" in sources
    assert "alsa_input.pci-0000_00_1f.3.analog-stereo" in sources
    assert len(sources) == 3


def test_parse_mic_sources_empty_input():
    assert _parse_mic_sources("") == []


def test_suggest_whisper_no_gpu_returns_cpu_safe_pair():
    model, compute = _suggest_whisper(None)
    assert (model, compute) == ("medium", "int8")


def test_suggest_whisper_high_vram_picks_large_float16():
    assert _suggest_whisper(8.0) == ("large-v3", "float16")
    assert _suggest_whisper(6.0) == ("large-v3", "float16")


def test_suggest_whisper_mid_vram_picks_large_int8():
    assert _suggest_whisper(4.0) == ("large-v3", "int8")
    assert _suggest_whisper(5.5) == ("large-v3", "int8")


def test_suggest_whisper_low_vram_picks_small():
    assert _suggest_whisper(2.0) == ("small", "int8")
    assert _suggest_whisper(0.5) == ("small", "int8")
