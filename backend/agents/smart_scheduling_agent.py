# =============================================================
# Hi-Tech Waste Management — Smart Job Scheduling Agent
# AI-powered job assignment, route optimization, conflict detection
# =============================================================

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select, func
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from geopy.distance import geodesic
    HAS_GEOPY = True
except ImportError:
    HAS_GEOPY = False
    geodesic = None

from models.job import Job, RecurringJobTemplate
from models.vehicle import Vehicle, Trip
from models.client import Client
from models.user import User

logger = logging.getLogger(__name__)


# =============================================================
# Scheduling Models
# =============================================================

class SchedulingConstraint(str, Enum):
    """Scheduling constraints to consider."""
    VEHICLE_CAPACITY = "vehicle_capacity"
    DRIVER_AVAILABILITY = "driver_availability"
    GEOGRAPHY_CLUSTERING = "geography_clustering"
    TIME_WINDOWS = "time_windows"
    WASTE_TYPE_COMPATIBILITY = "waste_type_compatibility"
    PRIORITY_ORDER = "priority_order"


class ConflictType(str, Enum):
    """Types of scheduling conflicts."""
    DOUBLE_BOOKED_VEHICLE = "double_booked_vehicle"
    DOUBLE_BOOKED_DRIVER = "double_booked_driver"
    CAPACITY_EXCEEDED = "capacity_exceeded"
    TIME_OVERLAP = "time_overlap"
    LOCATION_INFEASIBLE = "location_infeasible"
    PERMIT_EXPIRED = "permit_expired"


@dataclass
class VehicleAvailability:
    """Vehicle availability window."""
    vehicle_id: UUID
    date: date
    start_time: time
    end_time: time
    available_capacity_kg: float
    current_location: Tuple[float, float]  # lat, lng
    assigned_jobs: List[UUID] = field(default_factory=list)


@dataclass
class JobRequirements:
    """Requirements for scheduling a job."""
    job_id: UUID
    client_id: UUID
    job_type: str
    scheduled_date: date
    preferred_time_start: Optional[time] = None
    preferred_time_end: Optional[time] = None
    estimated_duration_minutes: int = 60
    quantity_kg: float = 0.0
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    location_address: str = ""
    waste_stream_types: List[str] = field(default_factory=list)
    priority: int = 1  # 1-5, higher = more urgent
    required_vehicle_type: Optional[str] = None
    required_permits: List[str] = field(default_factory=list)


@dataclass
class Assignment:
    """A job-vehicle-driver assignment."""
    job_id: UUID
    vehicle_id: UUID
    driver_id: Optional[UUID] = None
    scheduled_date: date = field(default_factory=date.today)
    estimated_start_time: time = field(default_factory=lambda: time(9, 0))
    estimated_end_time: time = field(default_factory=lambda: time(10, 0))
    route_order: int = 0
    confidence_score: float = 0.0  # 0-1 matching quality
    notes: str = ""


@dataclass
class RouteStop:
    """A stop in an optimized route."""
    stop_order: int
    job_id: UUID
    client_name: str
    address: str
    lat: Optional[float]
    lng: Optional[float]
    estimated_arrival: time
    estimated_duration: int  # minutes
    waste_type: str


@dataclass
class OptimizedRoute:
    """An optimized route for a vehicle."""
    vehicle_id: UUID
    vehicle_name: str
    driver_id: Optional[UUID]
    driver_name: Optional[str]
    date: date
    stops: List[RouteStop]
    total_distance_km: float
    total_duration_minutes: int
    start_time: time
    end_time: time
    efficiency_score: float  # 0-1


@dataclass
class Conflict:
    """A detected scheduling conflict."""
    conflict_type: ConflictType
    severity: str  # "critical", "warning", "info"
    description: str
    affected_jobs: List[UUID]
    affected_vehicles: List[UUID]
    affected_drivers: List[UUID]
    suggested_resolution: str


@dataclass
class ScheduleSuggestion:
    """A scheduling suggestion from the AI."""
    suggestion_type: str  # "assign", "reassign", "batch", "route", "conflict"
    priority: int  # 1-5
    description: str
    assignments: List[Assignment]
    affected_jobs: List[UUID]
    reasoning: str
    estimated_efficiency_gain: float  # percentage improvement


# =============================================================
# Smart Scheduling Agent
# =============================================================

class SmartSchedulingAgent:
    """
    AI agent for intelligent job scheduling and route optimization.
    
    Features:
    - Auto-assign jobs to optimal vehicles
    - Route optimization for multiple stops
    - Conflict detection (double-booking, capacity, permits)
    - Geography-based clustering
    - Priority-based scheduling
    """
    
    def __init__(self, db: AsyncSession, current_user: Dict[str, Any]):
        self.db = db
        self.current_user = current_user
        self.cache: Dict[str, Any] = {}
    
    async def get_unassigned_jobs(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        location_filter: Optional[str] = None
    ) -> List[JobRequirements]:
        """Get all unassigned jobs that need scheduling."""
        query = select(Job).where(
            and_(
                Job.status.in_(["draft", "confirmed"]),
                Job.assigned_vehicle_id.is_(None)
            )
        )
        
        if date_from:
            query = query.where(Job.scheduled_date >= date_from)
        if date_to:
            query = query.where(Job.scheduled_date <= date_to)
        if location_filter:
            query = query.where(Job.site_address.ilike(f"%{location_filter}%"))
        
        result = await self.db.execute(query)
        jobs = result.scalars().all()
        
        job_requirements = []
        for job in jobs:
            # Get client info for location
            client_result = await self.db.execute(
                select(Client).where(Client.id == job.client_id)
            )
            client = client_result.scalar_one_or_none()
            
            req = JobRequirements(
                job_id=job.id,
                client_id=job.client_id,
                job_type=job.job_type,
                scheduled_date=job.scheduled_date or date.today(),
                preferred_time_start=job.preferred_time_start,
                preferred_time_end=job.preferred_time_end,
                estimated_duration_minutes=job.estimated_duration_minutes or 60,
                quantity_kg=float(job.quantity_kg) if job.quantity_kg else 0.0,
                location_lat=client.latitude if client else None,
                location_lng=client.longitude if client else None,
                location_address=job.site_address or (client.billing_address if client else ""),
                waste_stream_types=[w.waste_type for w in job.waste_streams] if job.waste_streams else [],
                priority=job.priority or 1,
                required_vehicle_type=job.preferred_vehicle_type,
            )
            job_requirements.append(req)
        
        return job_requirements
    
    async def get_available_vehicles(
        self,
        target_date: date,
        vehicle_type: Optional[str] = None
    ) -> List[VehicleAvailability]:
        """Get vehicles available on a specific date."""
        query = select(Vehicle).where(
            and_(
                Vehicle.status.in_(["available", "active"]),
                Vehicle.is_active == True
            )
        )
        
        if vehicle_type:
            query = query.where(Vehicle.vehicle_type == vehicle_type)
        
        result = await self.db.execute(query)
        vehicles = result.scalars().all()
        
        availabilities = []
        for vehicle in vehicles:
            # Get existing assignments for this date
            assigned_jobs_result = await self.db.execute(
                select(Job).where(
                    and_(
                        Job.assigned_vehicle_id == vehicle.id,
                        Job.scheduled_date == target_date,
                        Job.status.notin_(["cancelled", "completed"])
                    )
                )
            )
            assigned_jobs = assigned_jobs_result.scalars().all()
            
            # Calculate remaining capacity
            used_capacity = sum(
                float(j.quantity_kg) for j in assigned_jobs if j.quantity_kg
            )
            available_capacity = float(vehicle.capacity_kg) - used_capacity if vehicle.capacity_kg else 1000.0
            
            # Calculate time windows
            work_start = time(8, 0)  # 8 AM
            work_end = time(18, 0)   # 6 PM
            
            # Adjust for existing assignments
            if assigned_jobs:
                # Simple approach: assume sequential scheduling
                total_duration = sum(
                    (j.estimated_duration_minutes or 60) + 30  # +30 min travel
                    for j in assigned_jobs
                )
                hours_used = total_duration / 60
                if hours_used >= 8:
                    continue  # Vehicle fully booked
            
            avail = VehicleAvailability(
                vehicle_id=vehicle.id,
                date=target_date,
                start_time=work_start,
                end_time=work_end,
                available_capacity_kg=max(0, available_capacity),
                current_location=(
                    vehicle.current_latitude or 5.4142,  # Default to Kulim area
                    vehicle.current_longitude or 100.5506
                ),
                assigned_jobs=[j.id for j in assigned_jobs]
            )
            availabilities.append(avail)
        
        return availabilities
    
    def calculate_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float
    ) -> float:
        """Calculate distance between two points in km."""
        if HAS_GEOPY and geodesic:
            try:
                return geodesic((lat1, lng1), (lat2, lng2)).kilometers
            except Exception:
                pass
        
        # Haversine formula for more accurate distance calculation
        R = 6371  # Earth's radius in km
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat/2) * math.sin(delta_lat/2) +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lng/2) * math.sin(delta_lng/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def score_assignment(
        self,
        job: JobRequirements,
        vehicle: VehicleAvailability,
        constraints: Set[SchedulingConstraint]
    ) -> float:
        """
        Score how well a job matches a vehicle (0-1, higher is better).
        """
        scores = []
        
        # Capacity match
        if SchedulingConstraint.VEHICLE_CAPACITY in constraints:
            if job.quantity_kg > vehicle.available_capacity_kg:
                return 0.0  # Can't fit
            capacity_utilization = job.quantity_kg / max(vehicle.available_capacity_kg, 1)
            scores.append(0.3 * (1 - abs(capacity_utilization - 0.8)))  # Prefer 80% utilization
        
        # Geography / proximity
        if SchedulingConstraint.GEOGRAPHY_CLUSTERING in constraints:
            if job.location_lat and job.location_lng:
                distance = self.calculate_distance(
                    vehicle.current_location[0],
                    vehicle.current_location[1],
                    job.location_lat,
                    job.location_lng
                )
                # Score based on distance (closer is better)
                proximity_score = max(0, 1 - (distance / 50))  # 50km threshold
                scores.append(0.4 * proximity_score)
        
        # Time window compatibility
        if SchedulingConstraint.TIME_WINDOWS in constraints:
            if job.preferred_time_start and job.preferred_time_end:
                # Check if fits in vehicle window
                fits = (
                    vehicle.start_time <= job.preferred_time_start and
                    vehicle.end_time >= job.preferred_time_end
                )
                scores.append(0.2 if fits else 0.1)
        
        # Priority bonus
        if SchedulingConstraint.PRIORITY_ORDER in constraints:
            scores.append(0.1 * (job.priority / 5))
        
        return sum(scores)
    
    async def suggest_job_assignments(
        self,
        jobs: Optional[List[JobRequirements]] = None,
        target_date: Optional[date] = None,
        constraints: Optional[Set[SchedulingConstraint]] = None
    ) -> ScheduleSuggestion:
        """
        Suggest optimal job-to-vehicle assignments.
        
        Uses a greedy algorithm with scoring:
        1. Sort jobs by priority and time requirements
        2. For each job, find best matching vehicle
        3. Return assignments with confidence scores
        """
        if constraints is None:
            constraints = {
                SchedulingConstraint.VEHICLE_CAPACITY,
                SchedulingConstraint.GEOGRAPHY_CLUSTERING,
                SchedulingConstraint.TIME_WINDOWS,
                SchedulingConstraint.PRIORITY_ORDER
            }
        
        target_date = target_date or date.today()
        
        if jobs is None:
            jobs = await self.get_unassigned_jobs(
                date_from=target_date,
                date_to=target_date
            )
        
        if not jobs:
            return ScheduleSuggestion(
                suggestion_type="assign",
                priority=1,
                description="No unassigned jobs found for the target date",
                assignments=[],
                affected_jobs=[],
                reasoning="All jobs are already assigned or no jobs scheduled for this date",
                estimated_efficiency_gain=0.0
            )
        
        # Get available vehicles
        vehicles = await self.get_available_vehicles(target_date)
        
        if not vehicles:
            return ScheduleSuggestion(
                suggestion_type="assign",
                priority=5,  # Critical - no vehicles available
                description="No vehicles available for the target date",
                assignments=[],
                affected_jobs=[j.job_id for j in jobs],
                reasoning="All vehicles are either fully booked or unavailable",
                estimated_efficiency_gain=0.0
            )
        
        # Sort jobs: priority desc, then by time window
        sorted_jobs = sorted(
            jobs,
            key=lambda j: (-j.priority, j.preferred_time_start or time(0, 0))
        )
        
        assignments = []
        used_vehicles: Dict[UUID, VehicleAvailability] = {v.vehicle_id: v for v in vehicles}
        
        for job in sorted_jobs:
            best_vehicle = None
            best_score = 0.0
            
            for vehicle_id, vehicle in used_vehicles.items():
                score = self.score_assignment(job, vehicle, constraints)
                if score > best_score:
                    best_score = score
                    best_vehicle = vehicle
            
            if best_vehicle and best_score > 0.3:  # Minimum threshold
                # Calculate timing
                if job.preferred_time_start:
                    est_start = job.preferred_time_start
                else:
                    # Default to vehicle start time + buffer
                    est_start = used_vehicles[best_vehicle.vehicle_id].start_time
                
                # Estimate end time
                duration = timedelta(minutes=job.estimated_duration_minutes)
                est_end = (
                    datetime.combine(date.today(), est_start) + duration
                ).time()
                
                assignment = Assignment(
                    job_id=job.job_id,
                    vehicle_id=best_vehicle.vehicle_id,
                    scheduled_date=target_date,
                    estimated_start_time=est_start,
                    estimated_end_time=est_end,
                    confidence_score=best_score,
                    notes=f"Matched based on capacity ({job.quantity_kg:.0f}kg), geography, and priority"
                )
                assignments.append(assignment)
                
                # Update vehicle availability
                used_vehicles[best_vehicle.vehicle_id].available_capacity_kg -= job.quantity_kg
                used_vehicles[best_vehicle.vehicle_id].start_time = est_end
        
        # Build suggestion
        unassigned_jobs = [j.job_id for j in sorted_jobs 
                          if j.job_id not in [a.job_id for a in assignments]]
        
        efficiency_gain = len(assignments) / len(jobs) * 100 if jobs else 0
        
        return ScheduleSuggestion(
            suggestion_type="assign",
            priority=3 if unassigned_jobs else 2,
            description=f"Suggested {len(assignments)} job assignments for {target_date}",
            assignments=assignments,
            affected_jobs=[a.job_id for a in assignments],
            reasoning=(
                f"Assigned {len(assignments)} of {len(jobs)} jobs using "
                f"capacity-based matching and geographic clustering. "
                f"{len(unassigned_jobs)} jobs could not be assigned due to capacity/availability constraints."
            ),
            estimated_efficiency_gain=efficiency_gain
        )
    
    async def optimize_route(
        self,
        vehicle_id: UUID,
        target_date: date,
        job_ids: Optional[List[UUID]] = None
    ) -> Optional[OptimizedRoute]:
        """
        Optimize the route for a vehicle's assigned jobs.
        
        Uses a nearest-neighbor approach for TSP-like optimization.
        """
        # Get vehicle info
        vehicle_result = await self.db.execute(
            select(Vehicle).where(Vehicle.id == vehicle_id)
        )
        vehicle = vehicle_result.scalar_one_or_none()
        
        if not vehicle:
            return None
        
        # Get jobs for this vehicle on this date
        if job_ids:
            jobs_query = select(Job).where(Job.id.in_(job_ids))
        else:
            jobs_query = select(Job).where(
                and_(
                    Job.assigned_vehicle_id == vehicle_id,
                    Job.scheduled_date == target_date,
                    Job.status.notin_(["cancelled", "completed"])
                )
            )
        
        jobs_result = await self.db.execute(jobs_query)
        jobs = jobs_result.scalars().all()
        
        if not jobs:
            return None
        
        # Get client info for each job
        stops_data = []
        for job in jobs:
            client_result = await self.db.execute(
                select(Client).where(Client.id == job.client_id)
            )
            client = client_result.scalar_one_or_none()
            
            lat = client.latitude if client else None
            lng = client.longitude if client else None
            
            stops_data.append({
                "job": job,
                "client": client,
                "lat": lat,
                "lng": lng,
                "address": job.site_address or (client.billing_address if client else "Unknown"),
            })
        
        # Simple nearest-neighbor route optimization
        # Start from vehicle's current location
        current_lat = vehicle.current_latitude or 5.4142
        current_lng = vehicle.current_longitude or 100.5506
        
        unvisited = stops_data.copy()
        route_stops = []
        total_distance = 0.0
        current_time = time(8, 0)  # Start at 8 AM
        
        stop_order = 1
        while unvisited:
            # Find nearest unvisited stop
            nearest = None
            min_distance = float('inf')
            
            for stop in unvisited:
                if stop["lat"] and stop["lng"]:
                    dist = self.calculate_distance(
                        current_lat, current_lng,
                        stop["lat"], stop["lng"]
                    )
                else:
                    dist = 999  # Unknown location - deprioritize
                
                if dist < min_distance:
                    min_distance = dist
                    nearest = stop
            
            if not nearest:
                break
            
            # Add to route
            travel_time = max(15, int(min_distance / 40 * 60))  # Assume 40 km/h average
            arrival_time = (
                datetime.combine(date.today(), current_time) + 
                timedelta(minutes=travel_time)
            ).time()
            
            job = nearest["job"]
            route_stop = RouteStop(
                stop_order=stop_order,
                job_id=job.id,
                client_name=nearest["client"].company_name if nearest["client"] else "Unknown",
                address=nearest["address"],
                lat=nearest["lat"],
                lng=nearest["lng"],
                estimated_arrival=arrival_time,
                estimated_duration=job.estimated_duration_minutes or 60,
                waste_type=job.waste_streams[0].waste_type if job.waste_streams else job.job_type.value
            )
            route_stops.append(route_stop)
            
            # Update for next iteration
            total_distance += min_distance
            current_lat = nearest["lat"] or current_lat
            current_lng = nearest["lng"] or current_lng
            
            # Add service time + travel buffer
            duration = timedelta(minutes=(job.estimated_duration_minutes or 60) + 15)
            current_time = (
                datetime.combine(date.today(), arrival_time) + duration
            ).time()
            
            unvisited.remove(nearest)
            stop_order += 1
        
        # Get driver info
        driver_result = await self.db.execute(
            select(User).where(User.id == vehicle.assigned_driver_id)
        )
        driver = driver_result.scalar_one_or_none()
        
        # Calculate efficiency (theoretical vs actual distance)
        if len(route_stops) > 1:
            # Simple efficiency: compare to random order
            theoretical_random = len(route_stops) * 20  # Assume 20km average between stops
            efficiency = min(1.0, theoretical_random / max(total_distance, 1))
        else:
            efficiency = 1.0
        
        return OptimizedRoute(
            vehicle_id=vehicle_id,
            vehicle_name=f"{vehicle.registration} ({vehicle.make} {vehicle.model})",
            driver_id=vehicle.assigned_driver_id,
            driver_name=driver.full_name if driver else None,
            date=target_date,
            stops=route_stops,
            total_distance_km=round(total_distance, 2),
            total_duration_minutes=(stop_order - 1) * 75,  # Rough estimate
            start_time=time(8, 0),
            end_time=current_time,
            efficiency_score=round(efficiency, 2)
        )
    
    async def detect_conflicts(
        self,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> List[Conflict]:
        """
        Detect scheduling conflicts.
        
        Checks for:
        - Double-booked vehicles
        - Double-booked drivers
        - Capacity exceeded
        - Overlapping time windows
        """
        conflicts = []
        date_from = date_from or date.today()
        date_to = date_to or date_from
        
        # Get all scheduled jobs in date range
        jobs_result = await self.db.execute(
            select(Job).where(
                and_(
                    Job.scheduled_date >= date_from,
                    Job.scheduled_date <= date_to,
                    Job.status.notin_(["cancelled", "completed"]),
                    Job.assigned_vehicle_id.isnot(None)
                )
            )
        )
        jobs = jobs_result.scalars().all()
        
        # Group by vehicle
        vehicle_jobs: Dict[UUID, List[Job]] = {}
        for job in jobs:
            vid = job.assigned_vehicle_id
            if vid not in vehicle_jobs:
                vehicle_jobs[vid] = []
            vehicle_jobs[vid].append(job)
        
        # Check for capacity conflicts
        for vid, vjobs in vehicle_jobs.items():
            vehicle_result = await self.db.execute(
                select(Vehicle).where(Vehicle.id == vid)
            )
            vehicle = vehicle_result.scalar_one_or_none()
            
            if vehicle and vehicle.capacity_kg:
                total_load = sum(
                    float(j.quantity_kg) for j in vjobs if j.quantity_kg
                )
                if total_load > float(vehicle.capacity_kg):
                    conflicts.append(Conflict(
                        conflict_type=ConflictType.CAPACITY_EXCEEDED,
                        severity="critical",
                        description=f"Vehicle {vehicle.registration} capacity exceeded: {total_load:.0f}kg / {vehicle.capacity_kg}kg",
                        affected_jobs=[j.id for j in vjobs],
                        affected_vehicles=[vid],
                        affected_drivers=[vehicle.assigned_driver_id] if vehicle.assigned_driver_id else [],
                        suggested_resolution=f"Redistribute {len(vjobs)} jobs to other vehicles or use larger vehicle"
                    ))
        
        # Check for driver conflicts (same driver, overlapping times)
        driver_jobs: Dict[UUID, List[Job]] = {}
        for job in jobs:
            # Get driver from assigned vehicle
            if job.assigned_vehicle_id:
                vehicle_result = await self.db.execute(
                    select(Vehicle).where(Vehicle.id == job.assigned_vehicle_id)
                )
                vehicle = vehicle_result.scalar_one_or_none()
                if vehicle and vehicle.assigned_driver_id:
                    did = vehicle.assigned_driver_id
                    if did not in driver_jobs:
                        driver_jobs[did] = []
                    driver_jobs[did].append(job)
        
        for did, djobs in driver_jobs.items():
            driver_result = await self.db.execute(
                select(User).where(User.id == did)
            )
            driver = driver_result.scalar_one_or_none()
            driver_name = driver.full_name if driver else str(did)[:8]
            
            # Check for same-day multiple assignments
            same_day_jobs = {}
            for job in djobs:
                day = job.scheduled_date
                if day not in same_day_jobs:
                    same_day_jobs[day] = []
                same_day_jobs[day].append(job)
            
            for day, day_jobs in same_day_jobs.items():
                if len(day_jobs) > 3:  # Warning threshold
                    total_duration = sum(
                        (j.estimated_duration_minutes or 60) + 30  # +travel
                        for j in day_jobs
                    )
                    if total_duration > 480:  # 8 hours
                        conflicts.append(Conflict(
                            conflict_type=ConflictType.DOUBLE_BOOKED_DRIVER,
                            severity="warning",
                            description=f"Driver {driver_name} over-scheduled on {day}: {total_duration/60:.1f} hours",
                            affected_jobs=[j.id for j in day_jobs],
                            affected_vehicles=[],
                            affected_drivers=[did],
                            suggested_resolution=f"Redistribute {len(day_jobs)} jobs across different drivers or days"
                        ))
        
        return conflicts
    
    async def batch_schedule_jobs(
        self,
        job_ids: List[UUID],
        target_date: date,
        strategy: str = "balanced"  # "balanced", "speed", "efficiency"
    ) -> ScheduleSuggestion:
        """
        Batch schedule multiple jobs using different strategies.
        
        Strategies:
        - balanced: Distribute evenly across available vehicles
        - speed: Minimize total time (assign to nearest vehicles)
        - efficiency: Maximize vehicle utilization
        """
        # Get job requirements
        jobs_result = await self.db.execute(
            select(Job).where(Job.id.in_(job_ids))
        )
        jobs = jobs_result.scalars().all()
        
        job_reqs = []
        for job in jobs:
            client_result = await self.db.execute(
                select(Client).where(Client.id == job.client_id)
            )
            client = client_result.scalar_one_or_none()
            
            req = JobRequirements(
                job_id=job.id,
                client_id=job.client_id,
                job_type=job.job_type,
                scheduled_date=target_date,
                quantity_kg=float(job.quantity_kg) if job.quantity_kg else 0.0,
                location_lat=client.latitude if client else None,
                location_lng=client.longitude if client else None,
                priority=job.priority or 1,
            )
            job_reqs.append(req)
        
        # Get available vehicles
        vehicles = await self.get_available_vehicles(target_date)
        
        if not vehicles:
            return ScheduleSuggestion(
                suggestion_type="batch",
                priority=5,
                description="No vehicles available for batch scheduling",
                assignments=[],
                affected_jobs=job_ids,
                reasoning="No available vehicles for the target date",
                estimated_efficiency_gain=0.0
            )
        
        assignments = []
        
        if strategy == "balanced":
            # Distribute round-robin weighted by capacity
            sorted_jobs = sorted(job_reqs, key=lambda j: -j.quantity_kg)
            sorted_vehicles = sorted(
                vehicles,
                key=lambda v: -v.available_capacity_kg
            )
            
            vehicle_idx = 0
            for job in sorted_jobs:
                # Try vehicles in round-robin
                attempts = 0
                while attempts < len(sorted_vehicles):
                    vehicle = sorted_vehicles[vehicle_idx % len(sorted_vehicles)]
                    
                    if job.quantity_kg <= vehicle.available_capacity_kg:
                        assignment = Assignment(
                            job_id=job.job_id,
                            vehicle_id=vehicle.vehicle_id,
                            scheduled_date=target_date,
                            confidence_score=0.7,
                            notes="Balanced distribution strategy"
                        )
                        assignments.append(assignment)
                        
                        # Update vehicle
                        vehicle.available_capacity_kg -= job.quantity_kg
                        break
                    
                    vehicle_idx += 1
                    attempts += 1
                
                vehicle_idx += 1
        
        elif strategy == "speed":
            # Assign to nearest available vehicle
            for job in job_reqs:
                best_vehicle = None
                min_distance = float('inf')
                
                for vehicle in vehicles:
                    if job.quantity_kg > vehicle.available_capacity_kg:
                        continue
                    
                    if job.location_lat and job.location_lng:
                        dist = self.calculate_distance(
                            vehicle.current_location[0],
                            vehicle.current_location[1],
                            job.location_lat,
                            job.location_lng
                        )
                        if dist < min_distance:
                            min_distance = dist
                            best_vehicle = vehicle
                
                if best_vehicle:
                    assignment = Assignment(
                        job_id=job.job_id,
                        vehicle_id=best_vehicle.vehicle_id,
                        scheduled_date=target_date,
                        confidence_score=0.8,
                        notes=f"Geographic proximity optimization ({min_distance:.1f}km)"
                    )
                    assignments.append(assignment)
                    best_vehicle.available_capacity_kg -= job.quantity_kg
        
        else:  # efficiency
            # Maximize vehicle utilization - fill vehicles completely
            sorted_vehicles = sorted(
                vehicles,
                key=lambda v: -v.available_capacity_kg
            )
            
            remaining_jobs = job_reqs.copy()
            
            for vehicle in sorted_vehicles:
                vehicle_load = 0.0
                
                # Greedily add jobs until capacity reached
                for job in remaining_jobs[:]:
                    if vehicle_load + job.quantity_kg <= vehicle.available_capacity_kg:
                        assignment = Assignment(
                            job_id=job.job_id,
                            vehicle_id=vehicle.vehicle_id,
                            scheduled_date=target_date,
                            confidence_score=0.75,
                            notes="Efficiency-optimized fill"
                        )
                        assignments.append(assignment)
                        vehicle_load += job.quantity_kg
                        remaining_jobs.remove(job)
        
        assigned_count = len(assignments)
        total_jobs = len(job_reqs)
        
        return ScheduleSuggestion(
            suggestion_type="batch",
            priority=2,
            description=f"Batch scheduled {assigned_count} jobs using '{strategy}' strategy",
            assignments=assignments,
            affected_jobs=[a.job_id for a in assignments],
            reasoning=(
                f"Used '{strategy}' strategy to assign {assigned_count} of {total_jobs} jobs. "
                f"{total_jobs - assigned_count} jobs could not be assigned due to constraints."
            ),
            estimated_efficiency_gain=(assigned_count / total_jobs * 100) if total_jobs else 0
        )
    
    async def apply_assignments(
        self,
        assignments: List[Assignment],
        commit: bool = True
    ) -> Dict[str, Any]:
        """
        Apply the suggested assignments to the database.
        
        Returns summary of applied changes.
        """
        applied = []
        failed = []
        
        for assignment in assignments:
            try:
                job_result = await self.db.execute(
                    select(Job).where(Job.id == assignment.job_id)
                )
                job = job_result.scalar_one_or_none()
                
                if job:
                    job.assigned_vehicle_id = assignment.vehicle_id
                    if assignment.driver_id:
                        # Note: Driver is assigned at vehicle level, not job level
                        pass
                    job.status = "confirmed"
                    
                    applied.append({
                        "job_id": str(assignment.job_id),
                        "vehicle_id": str(assignment.vehicle_id),
                        "scheduled_date": assignment.scheduled_date.isoformat()
                    })
                else:
                    failed.append({
                        "job_id": str(assignment.job_id),
                        "error": "Job not found"
                    })
                    
            except Exception as e:
                failed.append({
                    "job_id": str(assignment.job_id),
                    "error": str(e)
                })
        
        if commit and applied:
            await self.db.commit()
        
        return {
            "applied": len(applied),
            "failed": len(failed),
            "details": {"success": applied, "errors": failed}
        }


# =============================================================
# Pydantic Models for API
# =============================================================

class ScheduleRequest(BaseModel):
    """Request for scheduling suggestions."""
    target_date: date = Field(default_factory=date.today)
    job_ids: Optional[List[str]] = None
    location_filter: Optional[str] = None
    strategy: str = "balanced"  # balanced, speed, efficiency
    auto_assign: bool = False  # If true, apply suggestions immediately


class ScheduleResponse(BaseModel):
    """Response with scheduling suggestions."""
    suggestion_type: str
    priority: int
    description: str
    assignments: List[Dict[str, Any]]
    affected_jobs: List[str]
    reasoning: str
    estimated_efficiency_gain: float
    conflicts_detected: List[Dict[str, Any]] = []


class RouteRequest(BaseModel):
    """Request for route optimization."""
    vehicle_id: str
    target_date: date = Field(default_factory=date.today)
    job_ids: Optional[List[str]] = None


class RouteResponse(BaseModel):
    """Response with optimized route."""
    vehicle_id: str
    vehicle_name: str
    driver_name: Optional[str]
    date: date
    stops: List[Dict[str, Any]]
    total_distance_km: float
    total_duration_minutes: int
    start_time: str
    end_time: str
    efficiency_score: float


class ConflictResponse(BaseModel):
    """Response with detected conflicts."""
    conflicts: List[Dict[str, Any]]
    total_conflicts: int
    critical_count: int
    warning_count: int


class BatchScheduleRequest(BaseModel):
    """Request for batch scheduling."""
    job_ids: List[str]
    target_date: date
    strategy: str = "balanced"
    apply_immediately: bool = False


class BatchScheduleResponse(BaseModel):
    """Response from batch scheduling."""
    scheduled: int
    failed: int
    strategy_used: str
    assignments: List[Dict[str, Any]]
    unassigned_jobs: List[str]
