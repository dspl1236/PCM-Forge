# Service Log — Glovebox USB Design

## Concept

USB stick lives permanently in the glovebox. Each time a service
action runs, it appends an entry to `service_log.txt` with:
- VIN (from /HBpersistence/vin)
- Mileage (from cluster data)
- Action performed
- Date if available (or "no RTC" — mileage IS the timestamp)

## Mileage Sources (Priority Order)

### 1. LogBookSql.db
Path: `/HBpersistence/logbook/LogBookSql.db` (23,552 bytes)
Format: SQLite database
Contains: StartMileage and DestMileage for every trip
Query: `SELECT MAX(DestMileage) FROM trips;`
Tool: `qdbc` (QDB client, running on PCM, PID 147495)

### 2. hmetercounter.bin
Path: `/HBpersistence/logbook/hmetercounter.bin` (2 bytes)
Format: Binary (likely uint16 — hours or distance units)
Read: Simple `cat` or hex dump

### 3. CVALUE00020687 (Trip Counters)
Path: `/HBpersistence/CVALUE00020687.CVA` (488 bytes)
Contains: Trip distance, consumption, averages
Fields: CURRENT_MILEAGE_FKT (24-bit, up to 16M km)

### 4. CombiPresCtrl
Path: `/HBpersistence/NormalPersistencyFiles/generalPersistencyData_CombiPresCtrl`
Size: 162 bytes
Contains: Cached cluster state (mileage, SIA data)

### 5. BAP CURRENT_MILEAGE_FKT (future)
Once BAP channel is identified, read live odometer via BAP
STATUS message from cluster. Most accurate, real-time.

## Log Format

```
=== PCM-Forge Service Log ===
VIN: WP1AE2A28GLA64179

[38452 km] Oil service reset
[45123 km] Oil service reset
[52890 km] Inspection reset
```

## Implementation

The service reset script:
1. Reads VIN from `/HBpersistence/vin`
2. Reads mileage from best available source
3. Performs the BAP reset
4. Appends entry to `$USB/service_log.txt`
5. Log persists across USB insertions (file isn't overwritten)

If no mileage source works, logs "unknown km" — still useful
as a count of resets performed.
