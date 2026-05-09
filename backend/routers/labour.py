# =============================================================
# Hi-Tech Waste Management — Labour Router
# Staff registry, site assignments, shift scheduling, attendance.
# =============================================================

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models.labour import (
    ABSENCE_REASONS,
    EMPLOYMENT_TYPES,
    SHIFT_TYPES,
    STAFF_STATUSES,
    CheckInOut,
    MarkAbsent,
    Shift,
    ShiftAttendance,
    ShiftAttendanceRead,
    ShiftCreate,
    ShiftRead,
    SiteAssignment,
    SiteAssignmentCreate,
    SiteAssignmentMember,
    SiteAssignmentRead,
    StaffProfile,
    StaffProfileCreate,
    StaffProfileRead,
    StaffProfileUpdate,
    StaffStatusHistory,
)
from models.user import User
from routers.auth import get_current_user, require_roles
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# =============================================================
# Staff Registry Endpoints
# =============================================================


@router.get("/staff", response_model=List[StaffProfileRead])
async def list_staff(
    assignment_status: Optional[str] = Query(None),
    employment_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all staff members with optional filters."""
    q = select(StaffProfile)
    if assignment_status:
        q = q.where(StaffProfile.assignment_status == assignment_status)
    if employment_type:
        q = q.where(StaffProfile.employment_type == employment_type)
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/staff",
    response_model=StaffProfileRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def create_staff_profile(
    payload: StaffProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a staff profile linked to an existing user."""
    if payload.employment_type not in EMPLOYMENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"employment_type must be one of {sorted(EMPLOYMENT_TYPES)}",
        )
    # Check user exists
    user = await db.get(User, payload.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = StaffProfile(**payload.model_dump())
    db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile


@router.get("/staff/{profile_id}", response_model=StaffProfileRead)
async def get_staff_profile(
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await db.get(StaffProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Staff profile not found")
    return profile


@router.patch(
    "/staff/{profile_id}",
    response_model=StaffProfileRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def update_staff_profile(
    profile_id: uuid.UUID,
    payload: StaffProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = await db.get(StaffProfile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Staff profile not found")

    update_data = payload.model_dump(exclude_unset=True)

    # Track status change
    if "assignment_status" in update_data and update_data["assignment_status"] != profile.assignment_status:
        history = StaffStatusHistory(
            staff_profile_id=profile_id,
            previous_status=profile.assignment_status,
            new_status=update_data["assignment_status"],
            changed_by=current_user.id,
        )
        db.add(history)

    for field, value in update_data.items():
        setattr(profile, field, value)

    await db.flush()
    await db.refresh(profile)
    return profile


@router.get("/staff/{profile_id}/hours-summary")
async def get_hours_summary(
    profile_id: uuid.UUID,
    week_start: Optional[date] = Query(None, description="ISO date of week start (Monday)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return total scheduled hours for a staff member in a given week."""
    from datetime import timedelta

    if not week_start:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Get all shifts for this staff member in the week
    q = (
        select(ShiftAttendance, Shift)
        .join(Shift, ShiftAttendance.shift_id == Shift.id)
        .where(
            and_(
                ShiftAttendance.staff_profile_id == profile_id,
                Shift.shift_date >= week_start,
                Shift.shift_date <= week_end,
            )
        )
    )
    result = await db.execute(q)
    rows = result.all()

    total_minutes = 0
    for attendance, shift in rows:
        start_dt = datetime.combine(shift.shift_date, shift.start_time)
        end_dt = datetime.combine(shift.shift_date, shift.end_time)
        total_minutes += int((end_dt - start_dt).total_seconds() / 60)

    return {
        "staff_profile_id": str(profile_id),
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "total_scheduled_hours": round(total_minutes / 60, 2),
        "total_scheduled_minutes": total_minutes,
        "shift_count": len(rows),
    }


# =============================================================
# Site Assignment Endpoints
# =============================================================


@router.get(
    "/sites/{client_id}/assignments",
    response_model=List[SiteAssignmentRead],
)
async def list_site_assignments(
    client_id: uuid.UUID,
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        select(SiteAssignment)
        .where(SiteAssignment.client_id == client_id)
        .order_by(SiteAssignment.start_date.desc())
    )
    if active_only:
        q = q.where(SiteAssignment.is_active == True)
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/sites/assignments",
    response_model=SiteAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_roles("superadmin", "operations_manager", "field_supervisor"))
    ],
)
async def create_site_assignment(
    payload: SiteAssignmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a site assignment with team members."""
    # Validate at least one field_supervisor in members
    supervisor_roles = [m.role_at_site for m in payload.members]
    if "field_supervisor" not in supervisor_roles:
        raise HTTPException(
            status_code=422,
            detail="Site assignment must include at least one member with role 'field_supervisor'",
        )

    # Check for overlapping assignments for each member
    for member_input in payload.members:
        profile = await db.get(StaffProfile, member_input.staff_profile_id)
        if not profile:
            raise HTTPException(
                status_code=404,
                detail=f"Staff profile {member_input.staff_profile_id} not found",
            )
        if profile.assignment_status == "on_site" and profile.current_site_assignment_id:
            # Check date overlap
            existing_q = select(SiteAssignment).where(
                SiteAssignment.id == profile.current_site_assignment_id
            )
            result = await db.execute(existing_q)
            existing = result.scalar_one_or_none()
            if existing and existing.is_active:
                existing_end = existing.end_date or date(9999, 12, 31)
                new_end = payload.end_date or date(9999, 12, 31)
                if payload.start_date <= existing_end and new_end >= existing.start_date:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Staff member {member_input.staff_profile_id} has overlapping assignment at {existing.site_address}",
                    )

    assignment = SiteAssignment(
        client_id=payload.client_id,
        site_address=payload.site_address,
        supervisor_id=payload.supervisor_id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(assignment)
    await db.flush()

    # Add members and update their status
    for member_input in payload.members:
        member = SiteAssignmentMember(
            assignment_id=assignment.id,
            staff_profile_id=member_input.staff_profile_id,
            role_at_site=member_input.role_at_site,
        )
        db.add(member)

        profile = await db.get(StaffProfile, member_input.staff_profile_id)
        if profile:
            history = StaffStatusHistory(
                staff_profile_id=profile.id,
                previous_status=profile.assignment_status,
                new_status="on_site",
                changed_by=current_user.id,
            )
            db.add(history)
            profile.assignment_status = "on_site"
            profile.current_site_assignment_id = assignment.id

    await db.flush()
    await db.refresh(assignment)
    return assignment


@router.post(
    "/sites/assignments/{assignment_id}/close",
    response_model=SiteAssignmentRead,
    dependencies=[Depends(require_roles("superadmin", "operations_manager"))],
)
async def close_site_assignment(
    assignment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Close a site assignment and mark all members as available."""
    assignment = await db.get(SiteAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Site assignment not found")

    assignment.is_active = False
    assignment.end_date = date.today()

    # Update all active members to available
    members_q = select(SiteAssignmentMember).where(
        and_(
            SiteAssignmentMember.assignment_id == assignment_id,
            SiteAssignmentMember.left_at.is_(None),
        )
    )
    result = await db.execute(members_q)
    for member in result.scalars().all():
        member.left_at = datetime.now(timezone.utc)
        profile = await db.get(StaffProfile, member.staff_profile_id)
        if profile:
            history = StaffStatusHistory(
                staff_profile_id=profile.id,
                previous_status=profile.assignment_status,
                new_status="available",
                changed_by=current_user.id,
            )
            db.add(history)
            profile.assignment_status = "available"
            profile.current_site_assignment_id = None

    await db.flush()
    await db.refresh(assignment)
    return assignment


# =============================================================
# Shift Endpoints
# =============================================================


@router.get("/shifts", response_model=List[ShiftRead])
async def list_shifts(
    site_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Shift)
    if site_id:
        q = q.where(Shift.site_assignment_id == site_id)
    if date_from:
        q = q.where(Shift.shift_date >= date_from)
    if date_to:
        q = q.where(Shift.shift_date <= date_to)
    q = q.order_by(Shift.shift_date.desc(), Shift.start_time)
    result = await db.execute(q)
    return result.scalars().all()


@router.post(
    "/shifts",
    response_model=ShiftRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_roles("superadmin", "operations_manager", "field_supervisor"))
    ],
)
async def create_shift(
    payload: ShiftCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a shift and assign staff members."""
    # Validate end_time > start_time
    if payload.end_time <= payload.start_time:
        raise HTTPException(
            status_code=422,
            detail="end_time must be after start_time",
        )

    if payload.shift_type not in SHIFT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"shift_type must be one of {sorted(SHIFT_TYPES)}",
        )

    # Check for overlapping shifts for each staff member
    for staff_id in payload.staff_profile_ids:
        overlap_q = (
            select(ShiftAttendance)
            .join(Shift, ShiftAttendance.shift_id == Shift.id)
            .where(
                and_(
                    ShiftAttendance.staff_profile_id == staff_id,
                    Shift.shift_date == payload.shift_date,
                    Shift.site_assignment_id == payload.site_assignment_id,
                    Shift.start_time < payload.end_time,
                    Shift.end_time > payload.start_time,
                )
            )
        )
        result = await db.execute(overlap_q)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Staff member {staff_id} has an overlapping shift on {payload.shift_date}",
            )

    shift = Shift(
        site_assignment_id=payload.site_assignment_id,
        shift_date=payload.shift_date,
        shift_type=payload.shift_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        notes=payload.notes,
        created_by=current_user.id,
    )
    db.add(shift)
    await db.flush()

    # Create attendance records for each staff member
    for staff_id in payload.staff_profile_ids:
        attendance = ShiftAttendance(
            shift_id=shift.id,
            staff_profile_id=staff_id,
            status="present",
        )
        db.add(attendance)

    await db.flush()
    await db.refresh(shift)
    return shift


@router.post("/shifts/{shift_id}/check-in", response_model=ShiftAttendanceRead)
async def check_in(
    shift_id: uuid.UUID,
    payload: CheckInOut,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a staff member check-in for a shift."""
    q = select(ShiftAttendance).where(
        and_(
            ShiftAttendance.shift_id == shift_id,
            ShiftAttendance.staff_profile_id == payload.staff_profile_id,
        )
    )
    result = await db.execute(q)
    attendance = result.scalar_one_or_none()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    attendance.check_in_at = payload.timestamp or datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(attendance)
    return attendance


@router.post("/shifts/{shift_id}/check-out", response_model=ShiftAttendanceRead)
async def check_out(
    shift_id: uuid.UUID,
    payload: CheckInOut,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record a staff member check-out for a shift."""
    q = select(ShiftAttendance).where(
        and_(
            ShiftAttendance.shift_id == shift_id,
            ShiftAttendance.staff_profile_id == payload.staff_profile_id,
        )
    )
    result = await db.execute(q)
    attendance = result.scalar_one_or_none()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    attendance.check_out_at = payload.timestamp or datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(attendance)
    return attendance


@router.post("/shifts/{shift_id}/mark-absent", response_model=ShiftAttendanceRead)
async def mark_absent(
    shift_id: uuid.UUID,
    payload: MarkAbsent,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a staff member as absent for a shift."""
    if payload.absence_reason not in ABSENCE_REASONS:
        raise HTTPException(
            status_code=422,
            detail=f"absence_reason must be one of {sorted(ABSENCE_REASONS)}",
        )

    q = select(ShiftAttendance).where(
        and_(
            ShiftAttendance.shift_id == shift_id,
            ShiftAttendance.staff_profile_id == payload.staff_profile_id,
        )
    )
    result = await db.execute(q)
    attendance = result.scalar_one_or_none()
    if not attendance:
        raise HTTPException(status_code=404, detail="Attendance record not found")

    attendance.status = "absent"
    attendance.absence_reason = payload.absence_reason
    attendance.notes = payload.notes
    attendance.recorded_by = current_user.id
    await db.flush()
    await db.refresh(attendance)
    return attendance


# ── Attendance Query ──────────────────────────────────────────


@router.get("/attendance", response_model=List[ShiftAttendanceRead])
async def get_attendance(
    staff_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(ShiftAttendance).join(Shift, ShiftAttendance.shift_id == Shift.id)
    if staff_id:
        q = q.where(ShiftAttendance.staff_profile_id == staff_id)
    if date_from:
        q = q.where(Shift.shift_date >= date_from)
    if date_to:
        q = q.where(Shift.shift_date <= date_to)
    q = q.order_by(Shift.shift_date.desc())
    result = await db.execute(q)
    return result.scalars().all()
