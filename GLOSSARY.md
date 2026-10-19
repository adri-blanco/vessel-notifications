# Glossary

**Signal**: One decoded AIS message, from any message type. Most signals are discarded before they matter.

**Vessel**: A ship, identified by its MMSI alone. IMO is an optional attribute. A reflagged ship that gets a new MMSI is a new Vessel.

**Sighting**: A Signal that passed the Geofence check and opened a new Visit, so it was stored. Signals that are filtered out never become Sightings.

**Visit**: A run of Signals from one Vessel inside the Geofence with no silence longer than 30 minutes between them. Its end is inferred from that silence, because we only receive Signals and cannot see a Vessel leave. A Vessel gets one notification per Visit, on its first Signal, even if the Direction is empty.

**Small vessel**: A Vessel whose ship type is Fishing, Sailing or Pleasure craft. A Vessel with an unknown type is not small. Other criteria such as length may be added after testing.

**Notified**: Whether a Sighting was announced on Telegram. Every Visit is stored as a Sighting, but a Small vessel is only notified the first time it is ever seen.

**Geofence**: The polygon of interest. Only Signals positioned inside it count. With no polygon configured, every Signal counts.

**Direction**: Arriving or Departing, a property of a Sighting and not of the Vessel. For this port, a Vessel facing south (toward the right) is Arriving and one facing north is Departing. It is empty when the Signal does not give a clear answer (missing course, too slow, or otherwise unreliable).

**Non-vessel station**: A port, lighthouse or other aid to navigation that transmits AIS. It is never tracked, and Signals without a position are treated as coming from one.

**Enrichment**: Filling in a Vessel's attributes beyond what its position Signals carry (name, type, flag, photo). AIS static data is the first source in the chain, followed by external providers.
