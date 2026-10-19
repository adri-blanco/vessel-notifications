# Visits are inferred from silence, not from geofence exit

We only receive Signals, never a live position feed. A Vessel that leaves the Geofence or drops out of radio range simply stops transmitting to us. So a Visit ends when no Signal arrives for 30 minutes (configurable), and we notify once per Visit.

Alternatives considered: a fixed 5-minute dedup window, which re-notified every 5 minutes for a moored Vessel, and tracking geofence exit, which needs Signals we do not get once the Vessel is out of range.

Consequence: a Vessel that leaves and returns within the gap is one Visit, and a long radio dropout can split one real stay into two.
