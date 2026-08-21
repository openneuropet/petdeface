import socket

import pytest

from petdeface.qa import find_available_port


def test_find_available_port_skips_occupied_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied_socket:
        occupied_socket.bind(("", 0))
        occupied_socket.listen()
        occupied_port = occupied_socket.getsockname()[1]

        selected_port = find_available_port(occupied_port)

    assert selected_port > occupied_port


@pytest.mark.parametrize("port", [0, 80, 1023, 65536])
def test_find_available_port_rejects_invalid_port(port):
    with pytest.raises(ValueError, match="between 1024 and 65535"):
        find_available_port(port)
