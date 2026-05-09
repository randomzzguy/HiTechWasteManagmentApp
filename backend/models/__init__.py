# =============================================================
# Hi-Tech Waste Management — Models Package
# Import all ORM models here so SQLAlchemy's shared metadata
# is fully populated before create_all / Alembic runs.
# =============================================================

from .bsf import BSFBatch
from .client import Client, ClientWasteStream
from .destruction import DestructionJob
from .document import AgentEvent, Certificate, Document
from .equipment import (
    CompactionMachine,
    CompactorDeployment,
    CompactorMaintenanceLog,
    Container,
    ContainerFillReading,
    ContainerTransportLog,
    PickupTrigger,
)
from .esg import CarbonRecord
from .invoice import Invoice
from .job import Job, RecurringJobTemplate
from .labour import (
    Shift,
    ShiftAttendance,
    SiteAssignment,
    SiteAssignmentMember,
    StaffProfile,
    StaffStatusHistory,
)
from .disruption import DisruptionLog, DisruptionJobImpact
from .recyclable import DownstreamBuyer, RecyclableRecord
from .recycler_delivery import RecyclerDelivery
from .scheduled_waste import ConsignmentNote, ScheduledWasteBatch
from .user import User
from .vehicle import Trip, Vehicle
from .weighbridge import WeighbridgeRecord

__all__ = [
    "User",
    "Client",
    "ClientWasteStream",
    "Job",
    "RecurringJobTemplate",
    "Vehicle",
    "Trip",
    "WeighbridgeRecord",
    "ScheduledWasteBatch",
    "ConsignmentNote",
    "RecyclableRecord",
    "DownstreamBuyer",
    "DestructionJob",
    "BSFBatch",
    "CarbonRecord",
    "Invoice",
    "Certificate",
    "AgentEvent",
    "Document",
    # Operational Field Management
    "CompactionMachine",
    "CompactorDeployment",
    "CompactorMaintenanceLog",
    "Container",
    "ContainerFillReading",
    "ContainerTransportLog",
    "PickupTrigger",
    "StaffProfile",
    "StaffStatusHistory",
    "SiteAssignment",
    "SiteAssignmentMember",
    "Shift",
    "ShiftAttendance",
    "DisruptionLog",
    "DisruptionJobImpact",
    "RecyclerDelivery",
]
