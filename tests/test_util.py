from anker_solix_mcp.util import filter_devices, sanitize


def test_sanitize_redacts_sensitive_keys():
    data = {
        "name": "Solarbank",
        "auth_token": "abc123",
        "nested": {"password": "secret", "battery_soc": 87},
    }
    result = sanitize(data)
    assert result["name"] == "Solarbank"
    assert result["auth_token"] == "***redacted***"
    assert result["nested"]["password"] == "***redacted***"
    assert result["nested"]["battery_soc"] == 87


def test_sanitize_handles_lists_and_scalars():
    data = [{"token": "x"}, {"name": "ok"}, 42, "plain"]
    result = sanitize(data)
    assert result[0]["token"] == "***redacted***"
    assert result[1]["name"] == "ok"
    assert result[2] == 42
    assert result[3] == "plain"


def test_filter_devices_matches_type_field():
    devices = {
        "SN1": {"type": "solarbank", "name": "SB1"},
        "SN2": {"type": "smartmeter", "name": "SM1"},
    }
    result = filter_devices(devices, ("solarbank",))
    assert set(result) == {"SN1"}


def test_filter_devices_matches_model_code():
    devices = {
        "SN1": {"device_pn": "A17C0", "name": "Solarbank 2 E1600 Pro"},
        "SN2": {"device_pn": "X99Z9", "name": "Some Meter"},
    }
    result = filter_devices(devices, ("a17",))
    assert set(result) == {"SN1"}


def test_filter_devices_falls_back_to_all_when_no_match():
    devices = {"SN1": {"type": "unknown"}}
    result = filter_devices(devices, ("solarbank",))
    assert result == devices
