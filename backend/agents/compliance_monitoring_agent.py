# =============================================================
# Hi-Tech Waste Management — Compliance Monitoring Agent
# AI-powered compliance tracking, permit expiration alerts,
# and regulatory deadline monitoring
# =============================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.job import Job
from models.vehicle import Vehicle
from models.client import Client
from models.scheduled_waste import ScheduledWasteBatch, ConsignmentNote
from models.destruction import DestructionJob
from models.recyclable import DownstreamBuyer
from models.document import Certificate, AgentEvent

logger = logging.getLogger(__name__)


# =============================================================
# Compliance Monitoring Models
# =============================================================

class ComplianceType(str, Enum):
    """Types of compliance items to monitor."""
    SCHEDULED_WASTE_DEADLINE = "scheduled_waste_deadline"
    VEHICLE_ROAD_TAX = "vehicle_road_tax"
    VEHICLE_INSURANCE = "vehicle_insurance"
    VEHICLE_PUSPAKOM = "vehicle_puspakom"
    DRIVER_LICENSE = "driver_license"
    DOWNSTREAM_LICENSE = "downstream_license"
    DESTRUCTION_CERTIFICATE = "destruction_certificate"
    CONSIGNMENT_NOTE = "consignment_note"
    PERMIT_EWASTE = "permit_ewaste"
    PERMIT_SCHEDULED_WASTE = "permit_scheduled_waste"
    ESG_REPORTING = "esg_reporting"
    CUSTOM_COMPLIANCE = "custom_compliance"


class ComplianceStatus(str, Enum):
    """Status of a compliance item."""
    COMPLIANT = "compliant"           # All good
    WARNING = "warning"               # Due within 30 days
    CRITICAL = "critical"             # Due within 7 days or overdue
    EXPIRED = "expired"               # Past deadline
    PENDING = "pending"               # Awaiting action


class AlertPriority(str, Enum):
    """Priority levels for compliance alerts."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ComplianceItem:
    """A compliance item that needs monitoring."""
    item_id: UUID
    compliance_type: ComplianceType
    entity_type: str  # e.g., "vehicle", "scheduled_waste", "driver"
    entity_id: UUID
    entity_name: str  # Human-readable name
    description: str
    deadline: Optional[date] = None
    status: ComplianceStatus = ComplianceStatus.COMPLIANT
    days_remaining: Optional[int] = None
    regulation_reference: str = ""  # e.g., "DOE SW Guidelines 2024"
    required_action: str = ""
    assigned_to: Optional[UUID] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceAlert:
    """An alert about a compliance issue."""
    alert_id: str
    compliance_type: ComplianceType
    priority: AlertPriority
    title: str
    description: str
    affected_items: List[UUID]
    affected_entities: List[str]  # Human-readable names
    suggested_action: str
    auto_resolve_possible: bool = False
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceDashboard:
    """Overview of compliance status."""
    total_items: int
    compliant_count: int
    warning_count: int
    critical_count: int
    expired_count: int
    items_by_type: Dict[str, int]
    upcoming_deadlines: List[ComplianceItem]
    recent_alerts: List[ComplianceAlert]
    summary_text: str


@dataclass
class ComplianceReport:
    """Detailed compliance report for a period."""
    report_period: str  # e.g., "2026-Q2"
    generated_at: datetime
    items_checked: int
    violations_found: int
    violations_by_type: Dict[str, int]
    recommendations: List[str]
    regulatory_body: str  # e.g., "DOE Malaysia", "JPJ"


# =============================================================
# Smart Compliance Monitoring Agent
# =============================================================

class ComplianceMonitoringAgent:
    """
    AI agent for comprehensive compliance monitoring.
    
    Monitors:
    - Scheduled waste storage deadlines (DOE 90/180 day rule)
    - Vehicle permits (road tax, insurance, PUSPAKOM)
    - Driver license validity
    - Downstream buyer licenses
    - Destruction certificates
    - Consignment notes status
    - Custom compliance items
    
    Features:
    - Proactive deadline tracking
    - Automated alerts
    - Compliance dashboard
    - Regulatory reporting
    """
    
    # Malaysian DOE regulations
    SCHEDULED_WASTE_STORAGE_DAYS = 90  # Standard deadline
    SCHEDULED_WASTE_CRITICAL_DAYS = 60  # Warning threshold
    
    # Alert thresholds
    WARNING_DAYS = 30
    CRITICAL_DAYS = 7
    
    def __init__(self, db: AsyncSession, current_user: Dict[str, Any]):
        self.db = db
        self.current_user = current_user
        self.cache: Dict[str, Any] = {}
    
    async def check_scheduled_waste_compliance(
        self,
        client_id: Optional[UUID] = None,
        sw_code: Optional[str] = None
    ) -> List[ComplianceItem]:
        """
        Check scheduled waste batches against DOE storage deadlines.
        
        Malaysian DOE regulation: Max 90 days storage (180 for certain codes).
        """
        items = []
        
        query = select(ScheduledWasteBatch).where(
            ScheduledWasteBatch.status.in_(["in_storage", "dispatched"])
        )
        
        if client_id:
            query = query.where(ScheduledWasteBatch.client_id == client_id)
        if sw_code:
            query = query.where(ScheduledWasteBatch.sw_code == sw_code)
        
        result = await self.db.execute(query)
        batches = result.scalars().all()
        
        today = date.today()
        
        for batch in batches:
            # Calculate deadline
            deadline = batch.storage_start_date + timedelta(days=self.SCHEDULED_WASTE_STORAGE_DAYS)
            days_remaining = (deadline - today).days
            
            # Determine status
            if days_remaining < 0:
                status = ComplianceStatus.EXPIRED
            elif days_remaining <= self.CRITICAL_DAYS:
                status = ComplianceStatus.CRITICAL
            elif days_remaining <= self.WARNING_DAYS:
                status = ComplianceStatus.WARNING
            else:
                status = ComplianceStatus.COMPLIANT
            
            # Get client name
            client_result = await self.db.execute(
                select(Client).where(Client.id == batch.client_id)
            )
            client = client_result.scalar_one_or_none()
            client_name = client.company_name if client else "Unknown Client"
            
            item = ComplianceItem(
                item_id=batch.id,
                compliance_type=ComplianceType.SCHEDULED_WASTE_DEADLINE,
                entity_type="scheduled_waste_batch",
                entity_id=batch.id,
                entity_name=f"SW Batch {batch.sw_code} ({batch.waste_description[:30]}...)",
                description=f"Scheduled waste {batch.sw_code} stored since {batch.storage_start_date}",
                deadline=deadline,
                status=status,
                days_remaining=days_remaining,
                regulation_reference="DOE Scheduled Waste Management Guidelines 2024 (90-day rule)",
                required_action="Dispose of waste or obtain extension from DOE",
                metadata={
                    "sw_code": batch.sw_code,
                    "quantity_kg": str(batch.quantity_kg),
                    "storage_start": batch.storage_start_date.isoformat(),
                    "client_id": str(batch.client_id),
                    "client_name": client_name,
                }
            )
            items.append(item)
        
        return items
    
    async def check_vehicle_compliance(
        self,
        vehicle_id: Optional[UUID] = None
    ) -> List[ComplianceItem]:
        """
        Check vehicle permits and certifications.
        
        Monitors:
        - Road tax validity
        - Insurance expiry
        - PUSPAKOM inspection dates
        """
        items = []
        
        query = select(Vehicle).where(Vehicle.is_active == True)
        if vehicle_id:
            query = query.where(Vehicle.id == vehicle_id)
        
        result = await self.db.execute(query)
        vehicles = result.scalars().all()
        
        today = date.today()
        
        for vehicle in vehicles:
            vehicle_name = f"{vehicle.registration} ({vehicle.make} {vehicle.model})"
            
            # Check road tax (stored in JSON metadata or separate field)
            road_tax_expiry = self._extract_date_from_metadata(
                vehicle, "road_tax_expiry"
            )
            if road_tax_expiry:
                days_remaining = (road_tax_expiry - today).days
                status = self._get_status_from_days(days_remaining)
                
                items.append(ComplianceItem(
                    item_id=vehicle.id,
                    compliance_type=ComplianceType.VEHICLE_ROAD_TAX,
                    entity_type="vehicle",
                    entity_id=vehicle.id,
                    entity_name=vehicle_name,
                    description=f"Road tax for {vehicle.registration}",
                    deadline=road_tax_expiry,
                    status=status,
                    days_remaining=days_remaining,
                    regulation_reference="Road Transport Act 1987 (JPJ)",
                    required_action="Renew road tax at JPJ or Post Office",
                    metadata={"registration": vehicle.registration}
                ))
            
            # Check insurance
            insurance_expiry = self._extract_date_from_metadata(
                vehicle, "insurance_expiry"
            )
            if insurance_expiry:
                days_remaining = (insurance_expiry - today).days
                status = self._get_status_from_days(days_remaining)
                
                items.append(ComplianceItem(
                    item_id=vehicle.id,
                    compliance_type=ComplianceType.VEHICLE_INSURANCE,
                    entity_type="vehicle",
                    entity_id=vehicle.id,
                    entity_name=vehicle_name,
                    description=f"Insurance for {vehicle.registration}",
                    deadline=insurance_expiry,
                    status=status,
                    days_remaining=days_remaining,
                    regulation_reference="Motor Vehicles (Third Party Risks) Act 1963",
                    required_action="Renew vehicle insurance policy",
                    metadata={"registration": vehicle.registration}
                ))
            
            # Check PUSPAKOM inspection
            puspakom_expiry = self._extract_date_from_metadata(
                vehicle, "puspakom_expiry"
            )
            if puspakom_expiry:
                days_remaining = (puspakom_expiry - today).days
                status = self._get_status_from_days(days_remaining)
                
                items.append(ComplianceItem(
                    item_id=vehicle.id,
                    compliance_type=ComplianceType.VEHICLE_PUSPAKOM,
                    entity_type="vehicle",
                    entity_id=vehicle.id,
                    entity_name=vehicle_name,
                    description=f"PUSPAKOM inspection for {vehicle.registration}",
                    deadline=puspakom_expiry,
                    status=status,
                    days_remaining=days_remaining,
                    regulation_reference="Commercial Vehicle Licensing Board (CVLB) Regulations",
                    required_action="Book PUSPAKOM inspection appointment",
                    metadata={"registration": vehicle.registration}
                ))
        
        return items
    
    def _extract_date_from_metadata(
        self,
        obj: Any,
        field_name: str
    ) -> Optional[date]:
        """Extract a date from an object's metadata/attributes."""
        # Try direct attribute
        if hasattr(obj, field_name):
            val = getattr(obj, field_name)
            if isinstance(val, date) and not isinstance(val, datetime):
                return val
            if isinstance(val, datetime):
                return val.date()
        
        # Try metadata/JSON field
        if hasattr(obj, "metadata") and obj.metadata:
            if isinstance(obj.metadata, dict):
                date_str = obj.metadata.get(field_name)
                if date_str:
                    try:
                        if isinstance(date_str, str):
                            return date.fromisoformat(date_str)
                    except ValueError:
                        pass
        
        return None
    
    def _get_status_from_days(self, days_remaining: int) -> ComplianceStatus:
        """Determine compliance status based on days remaining."""
        if days_remaining < 0:
            return ComplianceStatus.EXPIRED
        elif days_remaining <= self.CRITICAL_DAYS:
            return ComplianceStatus.CRITICAL
        elif days_remaining <= self.WARNING_DAYS:
            return ComplianceStatus.WARNING
        else:
            return ComplianceStatus.COMPLIANT
    
    async def check_downstream_buyer_compliance(
        self
    ) -> List[ComplianceItem]:
        """
        Check downstream buyer/recycler license validity.
        """
        items = []
        
        result = await self.db.execute(
            select(DownstreamBuyer).where(DownstreamBuyer.is_active == True)
        )
        buyers = result.scalars().all()
        
        today = date.today()
        
        for buyer in buyers:
            # Check license expiry
            license_expiry = self._extract_date_from_metadata(
                buyer, "license_expiry_date"
            )
            
            if license_expiry:
                days_remaining = (license_expiry - today).days
                status = self._get_status_from_days(days_remaining)
                
                items.append(ComplianceItem(
                    item_id=buyer.id,
                    compliance_type=ComplianceType.DOWNSTREAM_LICENSE,
                    entity_type="downstream_buyer",
                    entity_id=buyer.id,
                    entity_name=buyer.company_name,
                    description=f"Recycling license for {buyer.company_name}",
                    deadline=license_expiry,
                    status=status,
                    days_remaining=days_remaining,
                    regulation_reference="DOE Environmental Quality Act 1974",
                    required_action="Contact buyer to renew recycling license",
                    metadata={
                        "license_number": buyer.license_number or "Unknown",
                        "material_types": buyer.material_types or [],
                    }
                ))
        
        return items
    
    async def check_destruction_certificate_compliance(
        self,
        days_pending_threshold: int = 7
    ) -> List[ComplianceItem]:
        """
        Check for destruction jobs awaiting certificates.
        
        Flags destruction jobs that:
        - Completed but no certificate issued
        - Certificate pending for > threshold days
        """
        items = []
        
        today = date.today()
        threshold_date = today - timedelta(days=days_pending_threshold)
        
        # Find destruction jobs completed but awaiting certificate
        result = await self.db.execute(
            select(DestructionJob).where(
                and_(
                    DestructionJob.destruction_date.isnot(None),
                    DestructionJob.certificate_issued == False,
                    DestructionJob.destruction_date <= threshold_date
                )
            )
        )
        jobs = result.scalars().all()
        
        for job in jobs:
            days_pending = (today - job.destruction_date).days
            
            status = ComplianceStatus.CRITICAL if days_pending > 14 else ComplianceStatus.WARNING
            
            items.append(ComplianceItem(
                item_id=job.id,
                compliance_type=ComplianceType.DESTRUCTION_CERTIFICATE,
                entity_type="destruction_job",
                entity_id=job.id,
                entity_name=f"Destruction Job {job.job_number or str(job.id)[:8]}",
                description=f"Certificate of destruction not issued after {days_pending} days",
                deadline=job.destruction_date + timedelta(days=days_pending_threshold),
                status=status,
                days_remaining=-days_pending,
                regulation_reference="Commercial practice - client contractual requirement",
                required_action="Generate Certificate of Destruction for client",
                metadata={
                    "destruction_date": job.destruction_date.isoformat(),
                    "destruction_method": job.destruction_method,
                    "days_pending": days_pending,
                }
            ))
        
        return items
    
    async def check_consignment_note_compliance(
        self
    ) -> List[ComplianceItem]:
        """
        Check consignment notes for proper tracking.
        
        Monitors:
        - Consignment notes not yet acknowledged by receiver
        - Long transit times
        """
        items = []
        
        today = date.today()
        
        # Find consignment notes in transit > 7 days
        result = await self.db.execute(
            select(ConsignmentNote).where(
                and_(
                    ConsignmentNote.status.in_(["issued", "in_transit"]),
                    ConsignmentNote.created_at <= datetime.now() - timedelta(days=7)
                )
            )
        )
        notes = result.scalars().all()
        
        for note in notes:
            days_in_transit = (today - note.created_at.date()).days
            
            if days_in_transit > 14:
                status = ComplianceStatus.CRITICAL
            elif days_in_transit > 7:
                status = ComplianceStatus.WARNING
            else:
                continue  # Skip if compliant
            
            items.append(ComplianceItem(
                item_id=note.id,
                compliance_type=ComplianceType.CONSIGNMENT_NOTE,
                entity_type="consignment_note",
                entity_id=note.id,
                entity_name=f"Consignment Note {note.note_number or str(note.id)[:8]}",
                description=f"Consignment note in transit for {days_in_transit} days",
                deadline=note.created_at.date() + timedelta(days=7),
                status=status,
                days_remaining=-days_in_transit,
                regulation_reference="DOE Scheduled Waste Tracking Requirements",
                required_action="Follow up with transporter/receiver for acknowledgement",
                metadata={
                    "note_number": note.note_number,
                    "status": note.status,
                    "days_in_transit": days_in_transit,
                }
            ))
        
        return items
    
    async def get_compliance_dashboard(
        self,
        compliance_types: Optional[List[ComplianceType]] = None
    ) -> ComplianceDashboard:
        """
        Get comprehensive compliance dashboard.
        """
        all_items = []
        
        # Check each compliance type
        if not compliance_types or ComplianceType.SCHEDULED_WASTE_DEADLINE in compliance_types:
            all_items.extend(await self.check_scheduled_waste_compliance())
        
        if not compliance_types or any(ct.value.startswith("vehicle") for ct in (compliance_types or [])):
            all_items.extend(await self.check_vehicle_compliance())
        
        if not compliance_types or ComplianceType.DOWNSTREAM_LICENSE in compliance_types:
            all_items.extend(await self.check_downstream_buyer_compliance())
        
        if not compliance_types or ComplianceType.DESTRUCTION_CERTIFICATE in compliance_types:
            all_items.extend(await self.check_destruction_certificate_compliance())
        
        if not compliance_types or ComplianceType.CONSIGNMENT_NOTE in compliance_types:
            all_items.extend(await self.check_consignment_note_compliance())
        
        # Calculate stats
        status_counts = {
            ComplianceStatus.COMPLIANT: 0,
            ComplianceStatus.WARNING: 0,
            ComplianceStatus.CRITICAL: 0,
            ComplianceStatus.EXPIRED: 0,
            ComplianceStatus.PENDING: 0,
        }
        
        items_by_type: Dict[str, int] = {}
        
        for item in all_items:
            status_counts[item.status] += 1
            items_by_type[item.compliance_type.value] = items_by_type.get(item.compliance_type.value, 0) + 1
        
        # Get upcoming deadlines (next 30 days)
        upcoming = [
            item for item in all_items
            if item.days_remaining is not None and 0 <= item.days_remaining <= 30
        ]
        upcoming.sort(key=lambda x: x.days_remaining or 999)
        
        # Generate alerts for critical/expired items
        alerts = self._generate_alerts(all_items)
        
        # Summary text
        summary = self._generate_summary_text(all_items, status_counts)
        
        return ComplianceDashboard(
            total_items=len(all_items),
            compliant_count=status_counts[ComplianceStatus.COMPLIANT],
            warning_count=status_counts[ComplianceStatus.WARNING],
            critical_count=status_counts[ComplianceStatus.CRITICAL],
            expired_count=status_counts[ComplianceStatus.EXPIRED],
            items_by_type=items_by_type,
            upcoming_deadlines=upcoming[:10],  # Top 10
            recent_alerts=alerts[:5],  # Top 5
            summary_text=summary
        )
    
    def _generate_alerts(self, items: List[ComplianceItem]) -> List[ComplianceAlert]:
        """Generate alerts from compliance items."""
        alerts = []
        
        # Group by type for consolidated alerts
        by_type: Dict[ComplianceType, List[ComplianceItem]] = {}
        for item in items:
            if item.status in [ComplianceStatus.CRITICAL, ComplianceStatus.EXPIRED]:
                if item.compliance_type not in by_type:
                    by_type[item.compliance_type] = []
                by_type[item.compliance_type].append(item)
        
        for comp_type, type_items in by_type.items():
            if len(type_items) == 1:
                item = type_items[0]
                alerts.append(ComplianceAlert(
                    alert_id=f"{comp_type.value}_{item.item_id}",
                    compliance_type=comp_type,
                    priority=AlertPriority.URGENT if item.status == ComplianceStatus.EXPIRED else AlertPriority.HIGH,
                    title=f"{comp_type.value.replace('_', ' ').title()} Alert",
                    description=item.description,
                    affected_items=[item.item_id],
                    affected_entities=[item.entity_name],
                    suggested_action=item.required_action,
                    auto_resolve_possible=False
                ))
            else:
                # Consolidated alert
                alerts.append(ComplianceAlert(
                    alert_id=f"{comp_type.value}_batch",
                    compliance_type=comp_type,
                    priority=AlertPriority.HIGH,
                    title=f"Multiple {comp_type.value.replace('_', ' ')} Issues",
                    description=f"{len(type_items)} items require immediate attention",
                    affected_items=[i.item_id for i in type_items],
                    affected_entities=[i.entity_name for i in type_items],
                    suggested_action=f"Address {len(type_items)} compliance items",
                    auto_resolve_possible=False
                ))
        
        return alerts
    
    def _generate_summary_text(
        self,
        items: List[ComplianceItem],
        status_counts: Dict[ComplianceStatus, int]
    ) -> str:
        """Generate human-readable summary."""
        total = len(items)
        
        if total == 0:
            return "No compliance items found. System appears to be properly configured."
        
        parts = []
        
        if status_counts[ComplianceStatus.COMPLIANT] == total:
            parts.append(f"All {total} compliance items are in good standing.")
        else:
            parts.append(f"Monitoring {total} compliance items:")
            
            if status_counts[ComplianceStatus.COMPLIANT] > 0:
                parts.append(f"- {status_counts[ComplianceStatus.COMPLIANT]} compliant")
            if status_counts[ComplianceStatus.WARNING] > 0:
                parts.append(f"- {status_counts[ComplianceStatus.WARNING]} warnings (due within 30 days)")
            if status_counts[ComplianceStatus.CRITICAL] > 0:
                parts.append(f"- {status_counts[ComplianceStatus.CRITICAL]} critical (due within 7 days)")
            if status_counts[ComplianceStatus.EXPIRED] > 0:
                parts.append(f"- {status_counts[ComplianceStatus.EXPIRED]} expired (immediate action required)")
        
        return " ".join(parts)
    
    async def generate_compliance_report(
        self,
        start_date: date,
        end_date: date,
        regulatory_body: str = "DOE Malaysia"
    ) -> ComplianceReport:
        """
        Generate a compliance report for a specific period.
        """
        items = []
        
        # Get all compliance items
        items.extend(await self.check_scheduled_waste_compliance())
        items.extend(await self.check_vehicle_compliance())
        items.extend(await self.check_downstream_buyer_compliance())
        items.extend(await self.check_destruction_certificate_compliance())
        items.extend(await self.check_consignment_note_compliance())
        
        # Filter by date range (items with deadlines in range)
        filtered_items = [
            item for item in items
            if item.deadline and start_date <= item.deadline <= end_date
        ]
        
        # Count violations
        violations = [i for i in filtered_items if i.status in [ComplianceStatus.CRITICAL, ComplianceStatus.EXPIRED]]
        violations_by_type: Dict[str, int] = {}
        for v in violations:
            violations_by_type[v.compliance_type.value] = violations_by_type.get(v.compliance_type.value, 0) + 1
        
        # Generate recommendations
        recommendations = self._generate_recommendations(filtered_items)
        
        period_str = f"{start_date.isoformat()} to {end_date.isoformat()}"
        
        return ComplianceReport(
            report_period=period_str,
            generated_at=datetime.now(),
            items_checked=len(filtered_items),
            violations_found=len(violations),
            violations_by_type=violations_by_type,
            recommendations=recommendations,
            regulatory_body=regulatory_body
        )
    
    def _generate_recommendations(self, items: List[ComplianceItem]) -> List[str]:
        """Generate actionable recommendations based on compliance items."""
        recommendations = []
        
        # Count by type
        type_counts: Dict[ComplianceType, int] = {}
        for item in items:
            if item.status in [ComplianceStatus.WARNING, ComplianceStatus.CRITICAL, ComplianceStatus.EXPIRED]:
                type_counts[item.compliance_type] = type_counts.get(item.compliance_type, 0) + 1
        
        # Generate recommendations
        if type_counts.get(ComplianceType.SCHEDULED_WASTE_DEADLINE, 0) > 0:
            count = type_counts[ComplianceType.SCHEDULED_WASTE_DEADLINE]
            recommendations.append(
                f"URGENT: {count} scheduled waste batches approaching or past DOE deadline. "
                "Prioritize disposal or request DOE extension immediately."
            )
        
        if type_counts.get(ComplianceType.VEHICLE_ROAD_TAX, 0) > 0:
            recommendations.append(
                f"Renew road tax for {type_counts[ComplianceType.VEHICLE_ROAD_TAX]} vehicles to avoid JPJ penalties."
            )
        
        if type_counts.get(ComplianceType.VEHICLE_INSURANCE, 0) > 0:
            recommendations.append(
                f"Update insurance coverage for {type_counts[ComplianceType.VEHICLE_INSURANCE]} vehicles before expiry."
            )
        
        if type_counts.get(ComplianceType.VEHICLE_PUSPAKOM, 0) > 0:
            recommendations.append(
                f"Schedule PUSPAKOM inspections for {type_counts[ComplianceType.VEHICLE_PUSPAKOM]} vehicles."
            )
        
        if type_counts.get(ComplianceType.DESTRUCTION_CERTIFICATE, 0) > 0:
            recommendations.append(
                f"Generate {type_counts[ComplianceType.DESTRUCTION_CERTIFICATE]} pending certificates of destruction for clients."
            )
        
        return recommendations
    
    async def get_compliance_summary_for_entity(
        self,
        entity_type: str,
        entity_id: UUID
    ) -> Dict[str, Any]:
        """
        Get compliance summary for a specific entity (client, vehicle, etc.).
        """
        items = []
        
        if entity_type == "client":
            items.extend(await self.check_scheduled_waste_compliance(client_id=entity_id))
        elif entity_type == "vehicle":
            items.extend(await self.check_vehicle_compliance(vehicle_id=entity_id))
        
        # Calculate summary
        total = len(items)
        by_status = {
            "compliant": len([i for i in items if i.status == ComplianceStatus.COMPLIANT]),
            "warning": len([i for i in items if i.status == ComplianceStatus.WARNING]),
            "critical": len([i for i in items if i.status == ComplianceStatus.CRITICAL]),
            "expired": len([i for i in items if i.status == ComplianceStatus.EXPIRED]),
        }
        
        next_deadline = None
        for item in sorted(items, key=lambda x: x.deadline or date.max):
            if item.deadline and item.status != ComplianceStatus.COMPLIANT:
                next_deadline = item.deadline.isoformat()
                break
        
        return {
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "total_compliance_items": total,
            "status_breakdown": by_status,
            "is_compliant": by_status["critical"] == 0 and by_status["expired"] == 0,
            "next_deadline": next_deadline,
            "items": [
                {
                    "type": i.compliance_type.value,
                    "status": i.status.value,
                    "description": i.description,
                    "deadline": i.deadline.isoformat() if i.deadline else None,
                    "days_remaining": i.days_remaining,
                    "action_required": i.required_action,
                }
                for i in items
            ]
        }


# =============================================================
# Pydantic Models for API
# =============================================================

class ComplianceDashboardRequest(BaseModel):
    """Request for compliance dashboard."""
    compliance_types: Optional[List[str]] = Field(
        None,
        description="Filter by specific compliance types"
    )
    client_id: Optional[str] = None
    vehicle_id: Optional[str] = None


class ComplianceDashboardResponse(BaseModel):
    """Compliance dashboard response."""
    total_items: int
    compliant_count: int
    warning_count: int
    critical_count: int
    expired_count: int
    items_by_type: Dict[str, int]
    upcoming_deadlines: List[Dict[str, Any]]
    recent_alerts: List[Dict[str, Any]]
    summary_text: str


class ComplianceCheckRequest(BaseModel):
    """Request for compliance check."""
    compliance_type: Optional[str] = None
    client_id: Optional[str] = None
    vehicle_id: Optional[str] = None
    days_lookahead: int = Field(default=30, ge=1, le=365)


class ComplianceCheckResponse(BaseModel):
    """Response from compliance check."""
    items_checked: int
    issues_found: int
    critical_count: int
    warning_count: int
    items: List[Dict[str, Any]]
    summary: str


class ComplianceReportRequest(BaseModel):
    """Request for compliance report."""
    start_date: date
    end_date: date
    regulatory_body: str = "DOE Malaysia"


class ComplianceReportResponse(BaseModel):
    """Compliance report response."""
    report_period: str
    generated_at: datetime
    items_checked: int
    violations_found: int
    violations_by_type: Dict[str, int]
    recommendations: List[str]
    regulatory_body: str


class ComplianceAlertResponse(BaseModel):
    """Compliance alerts response."""
    alerts: List[Dict[str, Any]]
    total_alerts: int
    urgent_count: int
    high_count: int
