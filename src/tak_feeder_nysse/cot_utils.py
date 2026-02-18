"""
CoT utilities for Nysse vehicles.
"""

import xml.etree.ElementTree as ET
from typing import Any
import pytak


def generate_nysse_cot(
    vehicle_ref: str,
    line_ref: str,
    lat: float,
    lon: float,
    **kwargs: Any,
) -> bytes:
    """
    Generate a Cursor on Target (CoT) XML message for a Nysse vehicle.
    """
    # Sidc: SFGPEVCMH--- -> a-f-G-E-V-C-M
    root = ET.Element("event")
    root.set("version", "2.0")
    root.set("type", "a-f-G-E-V-C-M")
    root.set("uid", f"nysse-{vehicle_ref}")
    root.set("how", "m-g")
    root.set("time", pytak.cot_time())
    root.set("start", pytak.cot_time())
    root.set("stale", pytak.cot_time(30))

    point = ET.SubElement(root, "point")
    point.set("lat", str(lat))
    point.set("lon", str(lon))
    point.set("hae", "0")
    point.set("ce", "10")
    point.set("le", "10")

    detail = ET.SubElement(root, "detail")

    track = ET.SubElement(detail, "track")
    track.set("course", str(kwargs.get("bearing", 0.0)))
    track.set("speed", str(kwargs.get("speed", 0.0)))

    contact = ET.SubElement(detail, "contact")
    contact.set("callsign", f"Nysse {vehicle_ref} ({line_ref})")

    remarks = ET.SubElement(detail, "remarks")
    remarks.text = (
        f"{kwargs.get('dest_city', 'Unknown')} {kwargs.get('dest_name', 'Unknown')}\n"
        f"Next stop: {kwargs.get('next_city', 'Unknown')} "
        f"{kwargs.get('next_stop_name', 'Unknown')} "
        f"{kwargs.get('next_stop_time', '--:--')}\n"
    )

    return ET.tostring(root)
