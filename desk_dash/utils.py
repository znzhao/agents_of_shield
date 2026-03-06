import socket
import logging
from typing import Tuple

logger = logging.getLogger(__name__)
def find_idle_port(start_port: int = 8050, max_attempts: int = 10) -> int:
    """
    Find an idle (available) port on the local machine.
    
    This function attempts to bind to ports starting from start_port.
    It tries multiple ports to find one that is available and not in use.
    
    Args:
        start_port: The port number to start searching from (default: 8050)
        max_attempts: Maximum number of ports to try (default: 10)
    
    Returns:
        int: An available port number
    
    Raises:
        RuntimeError: If no idle port is found after max_attempts tries
    """
    for offset in range(max_attempts):
        port = start_port + offset
        try:
            # Try to create a socket and bind to the port
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('127.0.0.1', port))
                logger.info(f"Found idle port: {port}")
                return port
        except OSError:
            logger.debug(f"Port {port} is in use, trying next port...")
            continue
    
    raise RuntimeError(
        f"Could not find an idle port after {max_attempts} attempts "
        f"(tried ports {start_port}-{start_port + max_attempts - 1})"
    )


def get_idle_host_port(
    preferred_port: int = 8050,
    preferred_host: str = '127.0.0.1',
    port_search_range: int = 10
) -> Tuple[str, int]:
    """
    Get an idle (available) host and port on the local machine.
    
    This function intelligently finds an available host and port for binding.
    It tries the preferred host first, and if that doesn't work, tries other
    localhost addresses. It also searches for available ports if the preferred
    port is in use.
    
    Args:
        preferred_port: The preferred port number (default: 8050)
        preferred_host: The preferred host address (default: '127.0.0.1')
        port_search_range: Number of ports to check (default: 10)
    
    Returns:
        Tuple[str, int]: A tuple of (host, port) that is available
    
    Raises:
        RuntimeError: If no idle port/host combination can be found
    """
    # List of hosts to try (in order of preference)
    hosts_to_try = [
        preferred_host,
        '127.0.0.1',
        'localhost',
        '0.0.0.0',  # Bind to all interfaces
    ]
    
    # Remove duplicates while preserving order
    seen = set()
    hosts_to_try = [h for h in hosts_to_try if not (h in seen or seen.add(h))]
    
    for host in hosts_to_try:
        try:
            # Try to bind to the preferred port first
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((host, preferred_port))
                logger.info(f"Found idle host:port = {host}:{preferred_port}")
                return (host, preferred_port)
        except OSError:
            logger.debug(
                f"Host {host} is not available or port {preferred_port} is in use"
            )
            
            # If preferred host/port fails, search for an idle port
            try:
                idle_port = find_idle_port(preferred_port, port_search_range)
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind((host, idle_port))
                    logger.info(f"Found idle host:port = {host}:{idle_port}")
                    return (host, idle_port)
            except (OSError, RuntimeError):
                logger.debug(f"Could not find idle port for host {host}")
                continue
    
    raise RuntimeError(
        "Could not find an idle host:port combination. "
        f"Tried hosts: {hosts_to_try} and ports {preferred_port}-{preferred_port + port_search_range - 1}"
    )
