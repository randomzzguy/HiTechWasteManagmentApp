# =============================================================
# Hi-Tech Waste Management — Fleet Router
# Vehicles, Trips, and Maintenance Management API
# =============================================================

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import get_settings
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.vehicle import (
    VEHICLE_STATUSES,
    VEHICLE_TYPES,
    MaintenanceLogCreate,
    MaintenanceLogRead,
    Trip,
    TripCreate,
    TripRead,
    TripUpdate,
    Vehicle,
    VehicleCreate,
    VehicleListItem,
    VehicleRead,
    VehicleUpdate,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth import get_current_user, require_roles

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# =============================================================
# In-memory maintenance log store
# In production this should be a dedicated DB table.
# =============================================================

_MAINTENANCE_LOGS: Dict[str, Dict[str, Any]] = {}

# Odometer threshold (km) to flag upcoming maintenance
ODOMETER_MAINTENANCE_THRESHOLD_KM = 5000


# =============================================================
# Helpers
# =============================================================


async def _get_vehicle_or_404(vehicle_id: uuid.UUID, db: AsyncSession) -> Vehicle:
    result = await db.execute(select(Vehicle).where(Vehicle.id == vehicle_id))
    vehicle = result.scalar_one_or_none()
    if vehicle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle {vehicle_id} not found",
        )
    return vehicle


async def _get_trip_or_404(trip_id: uuid.UUID, db: AsyncSession) -> Trip:
    result = await db.execute(select(Trip).where(Trip.id == trip_id))
    trip = result.scalar_one_or_none()
    if trip is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trip {trip_id} not found",
        )
    return trip


# =============================================================
# GET /vehicles — List vehicles
# =============================================================


@router.get(
    "/vehicles",
    response_model=Dict[str, Any],
    summary="List fleet vehicles",
    description=(
        "Returns a paginated list of vehicles. "
        "Filter by status (available | on_trip | maintenance | retired), "
        "vehicle_type, or assigned driver."
    ),
)
async def list_vehicles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="available | on_trip | maintenance | retired",
    ),
    vehicle_type: Optional[str] = Query(
        default=None,
        description="compactor | hook_loader | open_lorry | skip_truck | van",
    ),
    assigned_driver_id: Optional[uuid.UUID] = Query(
        default=None, description="Filter by assigned driver UUID"
    ),
    search: Optional[str] = Query(
        default=None, description="Partial match on registration, make, or model"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a paginated list of fleet vehicles with optional filters."""

    if status_filter and status_filter not in VEHICLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(VEHICLE_STATUSES)}",
        )
    if vehicle_type and vehicle_type not in VEHICLE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid vehicle_type. Must be one of: {sorted(VEHICLE_TYPES)}",
        )

    filters = []
    if status_filter:
        filters.append(Vehicle.status == status_filter)
    if vehicle_type:
        filters.append(Vehicle.vehicle_type == vehicle_type)
    if assigned_driver_id:
        filters.append(Vehicle.assigned_driver_id == assigned_driver_id)
    if search:
        like = f"%{search}%"
        filters.append(
            or_(
                Vehicle.registration.ilike(like),
                Vehicle.make.ilike(like),
                Vehicle.model.ilike(like),
            )
        )

    base_stmt = select(Vehicle)
    if filters:
        base_stmt = base_stmt.where(and_(*filters))

    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = base_stmt.order_by(Vehicle.registration).offset(skip).limit(limit)
    result = await db.execute(stmt)
    vehicles = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": [VehicleListItem.model_validate(v) for v in vehicles],
    }


# =============================================================
# POST /vehicles — Create vehicle
# =============================================================


@router.post(
    "/vehicles",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new vehicle",
    dependencies=[
        Depends(require_roles("superadmin", "management", "operations_manager"))
    ],
)
async def create_vehicle(
    payload: VehicleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> VehicleRead:
    """Register a new fleet vehicle."""

    if payload.vehicle_type not in VEHICLE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid vehicle_type. Must be one of: {sorted(VEHICLE_TYPES)}",
        )
    if payload.status not in VEHICLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(VEHICLE_STATUSES)}",
        )

    # Check registration uniqueness
    existing = await db.execute(
        select(Vehicle).where(Vehicle.registration == payload.registration.upper())
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle with registration '{payload.registration}' already exists",
        )

    vehicle = Vehicle(
        id=uuid.uuid4(),
        registration=payload.registration.upper(),
        vehicle_type=payload.vehicle_type,
        make=payload.make,
        model=payload.model,
        year=payload.year,
        capacity_kg=payload.capacity_kg,
        gps_device_id=payload.gps_device_id,
        assigned_driver_id=payload.assigned_driver_id,
        last_service_date=payload.last_service_date,
        next_service_date=payload.next_service_date,
        odometer_km=payload.odometer_km,
        status=payload.status,
        created_at=datetime.now(timezone.utc),
    )
    db.add(vehicle)
    await db.flush()
    await db.refresh(vehicle)

    logger.info(
        "Vehicle %s registered by user %s",
        vehicle.registration,
        current_user.get("sub"),
    )
    return VehicleRead.model_validate(vehicle)


# =============================================================
# GET /vehicles/{id} — Vehicle detail
# =============================================================


@router.get(
    "/vehicles/{vehicle_id}",
    response_model=VehicleRead,
    summary="Get vehicle detail",
)
async def get_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> VehicleRead:
    """Return full details of a single fleet vehicle."""
    vehicle = await _get_vehicle_or_404(vehicle_id, db)
    return VehicleRead.model_validate(vehicle)


# =============================================================
# PUT /vehicles/{id} — Update vehicle
# =============================================================


@router.put(
    "/vehicles/{vehicle_id}",
    response_model=VehicleRead,
    summary="Update vehicle details",
    dependencies=[
        Depends(require_roles("superadmin", "management", "operations_manager"))
    ],
)
async def update_vehicle(
    vehicle_id: uuid.UUID,
    payload: VehicleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> VehicleRead:
    """Partially update a fleet vehicle record."""
    vehicle = await _get_vehicle_or_404(vehicle_id, db)

    if payload.vehicle_type and payload.vehicle_type not in VEHICLE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid vehicle_type. Must be one of: {sorted(VEHICLE_TYPES)}",
        )
    if payload.status and payload.status not in VEHICLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status. Must be one of: {sorted(VEHICLE_STATUSES)}",
        )

    # Check registration uniqueness if being changed
    if payload.registration and payload.registration.upper() != vehicle.registration:
        existing = await db.execute(
            select(Vehicle).where(
                Vehicle.registration == payload.registration.upper(),
                Vehicle.id != vehicle_id,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Registration '{payload.registration}' is already in use",
            )

    update_data = payload.model_dump(exclude_unset=True)
    if "registration" in update_data:
        update_data["registration"] = update_data["registration"].upper()

    for field, value in update_data.items():
        setattr(vehicle, field, value)

    await db.flush()
    await db.refresh(vehicle)

    logger.info(
        "Vehicle %s updated by user %s",
        vehicle.registration,
        current_user.get("sub"),
    )
    return VehicleRead.model_validate(vehicle)


# =============================================================
# DELETE /vehicles/{id} — Retire vehicle (soft-delete)
# =============================================================


@router.delete(
    "/vehicles/{vehicle_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Retire a vehicle (soft-delete)",
    dependencies=[Depends(require_roles("superadmin", "management"))],
)
async def retire_vehicle(
    vehicle_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> None:
    """
    Retires a vehicle by setting its status to 'retired'.
    Records are never hard-deleted to preserve trip history.
    """
    vehicle = await _get_vehicle_or_404(vehicle_id, db)
    vehicle.status = "retired"
    await db.flush()
    logger.info(
        "Vehicle %s retired by user %s",
        vehicle.registration,
        current_user.get("sub"),
    )


# =============================================================
# GET /vehicles/{id}/trips — Trip history for a vehicle
# =============================================================


@router.get(
    "/vehicles/{vehicle_id}/trips",
    response_model=Dict[str, Any],
    summary="Trip history for a vehicle",
)
async def list_vehicle_trips(
    vehicle_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    driver_id: Optional[uuid.UUID] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the paginated trip history for a specific vehicle."""
    await _get_vehicle_or_404(vehicle_id, db)

    filters = [Trip.vehicle_id == vehicle_id]

    if date_from:
        dt_from = datetime(
            date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
        )
        filters.append(
            or_(Trip.departure_time >= dt_from, Trip.arrival_time >= dt_from)
        )
    if date_to:
        dt_to = datetime(
            date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=timezone.utc
        )
        filters.append(or_(Trip.departure_time <= dt_to, Trip.arrival_time <= dt_to))
    if driver_id:
        filters.append(Trip.driver_id == driver_id)

    count_stmt = select(func.count()).select_from(Trip).where(and_(*filters))
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar_one()

    stmt = (
        select(Trip)
        .where(and_(*filters))
        .order_by(Trip.departure_time.desc().nulls_last())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    trips = result.scalars().all()

    # Aggregate trip stats for this vehicle
    stats_stmt = select(
        func.count(Trip.id).label("total_trips"),
        func.coalesce(func.sum(Trip.distance_km), 0).label("total_km"),
        func.coalesce(func.sum(Trip.fuel_litres), 0).label("total_fuel"),
    ).where(Trip.vehicle_id == vehicle_id)
    stats_result = await db.execute(stats_stmt)
    stats_row = stats_result.one()

    return {
        "vehicle_id": str(vehicle_id),
        "total": total,
        "skip": skip,
        "limit": limit,
        "aggregate": {
            "total_trips": stats_row.total_trips,
            "total_distance_km": float(stats_row.total_km),
            "total_fuel_litres": float(stats_row.total_fuel),
        },
        "items": [TripRead.model_validate(t) for t in trips],
    }


# =============================================================
# POST /trips — Create a trip record
# =============================================================


@router.post(
    "/trips",
    response_model=TripRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new trip",
)
async def create_trip(
    payload: TripCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TripRead:
    """
    Record a new trip for a vehicle.

    - Validates that the vehicle exists and is not retired.
    - Auto-computes distance_km from odometer readings if not provided.
    - Updates the vehicle's odometer_km when end_odometer is provided.
    """
    # Validate vehicle exists and is not retired
    vehicle = await _get_vehicle_or_404(payload.vehicle_id, db)
    if vehicle.status == "retired":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle {vehicle.registration} is retired and cannot be assigned to trips",
        )

    # If job_id provided, validate job exists
    if payload.job_id:
        from models.job import Job

        job_result = await db.execute(select(Job).where(Job.id == payload.job_id))
        if job_result.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {payload.job_id} not found",
            )

    # Auto-compute distance from odometer if not supplied
    distance_km = payload.distance_km
    if (
        distance_km is None
        and payload.start_odometer is not None
        and payload.end_odometer is not None
    ):
        diff = payload.end_odometer - payload.start_odometer
        if diff >= 0:
            distance_km = diff

    trip = Trip(
        id=uuid.uuid4(),
        job_id=payload.job_id,
        vehicle_id=payload.vehicle_id,
        driver_id=payload.driver_id,
        start_odometer=payload.start_odometer,
        end_odometer=payload.end_odometer,
        distance_km=distance_km,
        fuel_litres=payload.fuel_litres,
        departure_time=payload.departure_time,
        arrival_time=payload.arrival_time,
        gps_track=payload.gps_track,
        notes=payload.notes,
    )
    db.add(trip)

    # Update vehicle odometer if end reading provided
    if payload.end_odometer is not None:
        if vehicle.odometer_km is None or payload.end_odometer > vehicle.odometer_km:
            vehicle.odometer_km = payload.end_odometer

    # Update vehicle status based on trip timing
    if payload.departure_time and not payload.arrival_time:
        vehicle.status = "on_trip"
    elif payload.arrival_time and vehicle.status == "on_trip":
        vehicle.status = "available"

    await db.flush()
    await db.refresh(trip)

    logger.info(
        "Trip created for vehicle %s by user %s",
        vehicle.registration,
        current_user.get("sub"),
    )
    return TripRead.model_validate(trip)


# =============================================================
# GET /trips/{id} — Trip detail
# =============================================================


@router.get(
    "/trips/{trip_id}",
    response_model=TripRead,
    summary="Get trip detail",
)
async def get_trip(
    trip_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TripRead:
    """Return full details of a single trip record."""
    trip = await _get_trip_or_404(trip_id, db)
    return TripRead.model_validate(trip)


# =============================================================
# PUT /trips/{id} — Update trip (e.g. record arrival)
# =============================================================


@router.put(
    "/trips/{trip_id}",
    response_model=TripRead,
    summary="Update a trip record",
)
async def update_trip(
    trip_id: uuid.UUID,
    payload: TripUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> TripRead:
    """
    Update a trip record.

    Typically used to record trip completion:
    - Set `end_odometer` and `arrival_time` when the driver returns.
    - Optionally upload `gps_track` data.
    - Updates the vehicle odometer automatically.
    """
    trip = await _get_trip_or_404(trip_id, db)

    update_data = payload.model_dump(exclude_unset=True)

    # Recompute distance if odometer updated but distance not provided
    if (
        "end_odometer" in update_data
        and "distance_km" not in update_data
        and trip.start_odometer is not None
    ):
        diff = update_data["end_odometer"] - trip.start_odometer
        if diff >= 0:
            update_data["distance_km"] = diff

    for field, value in update_data.items():
        setattr(trip, field, value)

    # Update vehicle odometer if this trip now has a higher end reading
    if payload.end_odometer is not None:
        vehicle = await _get_vehicle_or_404(trip.vehicle_id, db)
        if vehicle.odometer_km is None or payload.end_odometer > vehicle.odometer_km:
            vehicle.odometer_km = payload.end_odometer
        if payload.arrival_time and vehicle.status == "on_trip":
            vehicle.status = "available"

    await db.flush()
    await db.refresh(trip)
    return TripRead.model_validate(trip)


# =============================================================
# GET /maintenance/due — Vehicles due for maintenance
# =============================================================


@router.get(
    "/maintenance/due",
    response_model=Dict[str, Any],
    summary="List vehicles due for maintenance",
    description=(
        "Returns vehicles where next_service_date is within the next 30 days, "
        "or where the odometer is within 5,000 km of the last recorded service interval."
    ),
)
async def list_maintenance_due(
    days_ahead: int = Query(
        default=30,
        ge=1,
        le=180,
        description="Look-ahead window in days for service date",
    ),
    include_retired: bool = Query(
        default=False, description="Include retired vehicles in the results"
    ),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Identify vehicles approaching or overdue for scheduled maintenance.

    A vehicle is flagged when either:
    1. `next_service_date` is within `days_ahead` days (or already past).
    2. `odometer_km` is within {ODOMETER_MAINTENANCE_THRESHOLD_KM} km of the
       next service odometer (if tracked).
    """
    today = date.today()
    cutoff_date = today + timedelta(days=days_ahead)

    filters = [Vehicle.next_service_date <= cutoff_date]
    if not include_retired:
        filters.append(Vehicle.status != "retired")

    stmt = select(Vehicle).where(and_(*filters)).order_by(Vehicle.next_service_date)
    result = await db.execute(stmt)
    vehicles_due_by_date = result.scalars().all()

    # Collect IDs already flagged to avoid double-counting
    flagged_ids = {v.id for v in vehicles_due_by_date}

    # Flag by items — in a production system you'd store the target odometer
    # on the vehicle. Here we flag anything that hasn't had a service logged
    # and has high odometer (> 80,000 km as a simple heuristic).
    odometer_stmt = select(Vehicle).where(
        and_(
            Vehicle.odometer_km >= 80000,
            Vehicle.status != "retired" if not include_retired else True,
        )
    )
    odo_result = await db.execute(odometer_stmt)
    odo_vehicles = [v for v in odo_result.scalars().all() if v.id not in flagged_ids]

    def _enrich(v: Vehicle) -> Dict[str, Any]:
        days_until: Optional[int] = None
        overdue = False
        if v.next_service_date:
            days_until = (v.next_service_date - today).days
            overdue = days_until < 0

        severity = "info"
        if overdue:
            severity = "critical"
        elif days_until is not None and days_until <= 7:
            severity = "critical"
        elif days_until is not None and days_until <= 14:
            severity = "warning"

        return {
            "id": str(v.id),
            "registration": v.registration,
            "vehicle_type": v.vehicle_type,
            "make": v.make,
            "model": v.model,
            "status": v.status,
            "next_service_date": v.next_service_date.isoformat()
            if v.next_service_date
            else None,
            "last_service_date": v.last_service_date.isoformat()
            if v.last_service_date
            else None,
            "odometer_km": float(v.odometer_km) if v.odometer_km else None,
            "days_until_service": days_until,
            "is_overdue": overdue,
            "severity": severity,
            "flag_reason": "service_date" if v in vehicles_due_by_date else "odometer",
        }

    all_flagged = [_enrich(v) for v in vehicles_due_by_date] + [
        _enrich(v) for v in odo_vehicles
    ]
    # Sort: overdue first, then by days_until ascending
    all_flagged.sort(
        key=lambda x: (
            not x["is_overdue"],
            x["days_until_service"] if x["days_until_service"] is not None else 9999,
        )
    )

    return {
        "total": len(all_flagged),
        "days_ahead": days_ahead,
        "as_of_date": today.isoformat(),
        "items": all_flagged,
    }


# =============================================================
# POST /maintenance/logs — Log a maintenance event
# =============================================================


@router.post(
    "/maintenance/logs",
    status_code=status.HTTP_201_CREATED,
    summary="Log a vehicle maintenance event",
    dependencies=[
        Depends(require_roles("superadmin", "management", "operations_manager"))
    ],
)
async def log_maintenance(
    payload: MaintenanceLogCreate,
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> MaintenanceLogRead:
    """
    Records a maintenance event for a vehicle and updates
    the vehicle's `last_service_date`, `next_service_date`,
    and `odometer_km` fields accordingly.
    """
    vehicle = await _get_vehicle_or_404(payload.vehicle_id, db)

    # Update vehicle service dates and odometer
    vehicle.last_service_date = payload.service_date
    if payload.next_service_date:
        vehicle.next_service_date = payload.next_service_date
    if payload.odometer_at_service_km is not None:
        if (
            vehicle.odometer_km is None
            or payload.odometer_at_service_km >= vehicle.odometer_km
        ):
            vehicle.odometer_km = payload.odometer_at_service_km

    # Persist to in-memory log
    log_id = str(uuid.uuid4())
    log_entry: Dict[str, Any] = {
        "id": log_id,
        "vehicle_id": str(payload.vehicle_id),
        "service_date": payload.service_date.isoformat(),
        "service_type": payload.service_type,
        "odometer_at_service_km": float(payload.odometer_at_service_km)
        if payload.odometer_at_service_km
        else None,
        "next_service_date": payload.next_service_date.isoformat()
        if payload.next_service_date
        else None,
        "next_service_odometer_km": float(payload.next_service_odometer_km)
        if payload.next_service_odometer_km
        else None,
        "cost_myr": float(payload.cost_myr) if payload.cost_myr else None,
        "workshop": payload.workshop,
        "notes": payload.notes,
        "performed_by": payload.performed_by,
        "logged_by": current_user.get("sub"),
        "logged_at": datetime.now(timezone.utc).isoformat(),
    }
    _MAINTENANCE_LOGS[log_id] = log_entry
    await db.flush()

    logger.info(
        "Maintenance logged for vehicle %s | type=%s | by user %s",
        vehicle.registration,
        payload.service_type,
        current_user.get("sub"),
    )

    return MaintenanceLogRead(
        id=uuid.UUID(log_id),
        vehicle_id=payload.vehicle_id,
        service_date=payload.service_date,
        service_type=payload.service_type,
        odometer_at_service_km=payload.odometer_at_service_km,
        next_service_date=payload.next_service_date,
        next_service_odometer_km=payload.next_service_odometer_km,
        cost_myr=payload.cost_myr,
        workshop=payload.workshop,
        notes=payload.notes,
        performed_by=payload.performed_by,
        logged_at=datetime.now(timezone.utc),
    )


# =============================================================
# GET /maintenance/logs — List maintenance logs
# =============================================================


@router.get(
    "/maintenance/logs",
    response_model=Dict[str, Any],
    summary="List all maintenance logs",
)
async def list_maintenance_logs(
    vehicle_id: Optional[uuid.UUID] = Query(
        default=None, description="Filter by vehicle UUID"
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return all maintenance log entries, optionally filtered by vehicle."""
    logs: List[Dict[str, Any]] = list(_MAINTENANCE_LOGS.values())

    if vehicle_id:
        logs = [lg for lg in logs if lg.get("vehicle_id") == str(vehicle_id)]

    # Sort by service_date descending
    logs.sort(key=lambda x: x.get("service_date", ""), reverse=True)

    total = len(logs)
    paginated = logs[skip : skip + limit]

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "items": paginated,
    }


# =============================================================
# GET /maintenance/logs/{log_id} — Single maintenance log entry
# =============================================================


@router.get(
    "/maintenance/logs/{log_id}",
    summary="Get a maintenance log entry",
)
async def get_maintenance_log(
    log_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a single maintenance log entry by ID."""
    entry = _MAINTENANCE_LOGS.get(log_id)
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance log {log_id!r} not found",
        )
    return entry


# =============================================================
# GET /stats — Fleet stats alias
# =============================================================


@router.get(
    "/stats",
    response_model=Dict[str, Any],
    summary="Fleet statistics",
    description="Alias for /stats/fleet-utilisation for frontend compatibility.",
    include_in_schema=False,
)
async def fleet_stats_alias(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fleet stats alias endpoint - delegates to fleet_utilisation_stats."""
    return await fleet_utilisation_stats(date_from, date_to, db, current_user)


# =============================================================
# GET /stats/fleet-utilisation — Fleet utilisation stats
# =============================================================


@router.get(
    "/stats/fleet-utilisation",
    response_model=Dict[str, Any],
    summary="Fleet utilisation statistics",
    description=(
        "Returns fleet-wide utilisation metrics: "
        "active vs idle vs maintenance breakdown, "
        "average trip distance, and top vehicles by distance."
    ),
)
async def fleet_utilisation_stats(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Aggregate fleet utilisation metrics."""

    # Status distribution
    status_stmt = select(
        Vehicle.status,
        func.count(Vehicle.id).label("cnt"),
    ).group_by(Vehicle.status)
    status_result = await db.execute(status_stmt)
    status_dist = {row.status: row.cnt for row in status_result}

    # Vehicle type distribution
    type_stmt = select(
        Vehicle.vehicle_type,
        func.count(Vehicle.id).label("cnt"),
    ).group_by(Vehicle.vehicle_type)
    type_result = await db.execute(type_stmt)
    type_dist = {row.vehicle_type: row.cnt for row in type_result}

    total_vehicles = sum(status_dist.values())

    # Trip aggregations
    trip_filters = []
    if date_from:
        trip_filters.append(
            Trip.departure_time
            >= datetime(
                date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
            )
        )
    if date_to:
        trip_filters.append(
            Trip.departure_time
            <= datetime(
                date_to.year,
                date_to.month,
                date_to.day,
                23,
                59,
                59,
                tzinfo=timezone.utc,
            )
        )

    trip_agg_stmt = select(
        func.count(Trip.id).label("total_trips"),
        func.coalesce(func.sum(Trip.distance_km), 0).label("total_km"),
        func.coalesce(func.sum(Trip.fuel_litres), 0).label("total_fuel"),
        func.coalesce(func.avg(Trip.distance_km), 0).label("avg_km"),
    )
    if trip_filters:
        trip_agg_stmt = trip_agg_stmt.where(and_(*trip_filters))

    trip_result = await db.execute(trip_agg_stmt)
    trip_row = trip_result.one()

    # Top 5 vehicles by distance
    top_stmt = (
        select(
            Trip.vehicle_id,
            func.count(Trip.id).label("trip_count"),
            func.coalesce(func.sum(Trip.distance_km), 0).label("total_km"),
        )
        .group_by(Trip.vehicle_id)
        .order_by(func.sum(Trip.distance_km).desc().nulls_last())
        .limit(5)
    )
    if trip_filters:
        top_stmt = top_stmt.where(and_(*trip_filters))
    top_result = await db.execute(top_stmt)

    top_vehicles = []
    for row in top_result:
        v_result = await db.execute(select(Vehicle).where(Vehicle.id == row.vehicle_id))
        v = v_result.scalar_one_or_none()
        top_vehicles.append(
            {
                "vehicle_id": str(row.vehicle_id),
                "registration": v.registration if v else "Unknown",
                "vehicle_type": v.vehicle_type if v else "Unknown",
                "trip_count": row.trip_count,
                "total_km": float(row.total_km),
            }
        )

    return {
        "total_vehicles": total_vehicles,
        "status_distribution": status_dist,
        "type_distribution": type_dist,
        "utilisation_rate_pct": round(
            status_dist.get("on_trip", 0) / total_vehicles * 100, 2
        )
        if total_vehicles > 0
        else 0,
        "period_from": date_from.isoformat() if date_from else None,
        "period_to": date_to.isoformat() if date_to else None,
        "trip_aggregate": {
            "total_trips": trip_row.total_trips,
            "total_distance_km": float(trip_row.total_km),
            "total_fuel_litres": float(trip_row.total_fuel),
            "avg_trip_distance_km": float(trip_row.avg_km),
        },
        "top_vehicles_by_distance": top_vehicles,
        "maintenance_logs_count": len(_MAINTENANCE_LOGS),
    }
