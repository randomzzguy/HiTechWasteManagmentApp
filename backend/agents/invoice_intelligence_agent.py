# =============================================================
# Hi-Tech Waste Management — Invoice Intelligence Agent
# AI-powered aging reports, collection strategies, and
# predictive payment risk scoring
# =============================================================

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.invoice import Invoice, INVOICE_STATUSES, PaymentRecord
from models.client import Client

logger = logging.getLogger(__name__)


# =============================================================
# Invoice Intelligence Models
# =============================================================

class AgingBucket(str, Enum):
    """Standard aging buckets."""
    CURRENT = "current"           # 0-30 days
    BUCKET_31_60 = "31-60"        # 31-60 days
    BUCKET_61_90 = "61-90"        # 61-90 days
    BUCKET_91_120 = "91-120"      # 91-120 days
    BUCKET_120_PLUS = "120+"      # Over 120 days


class RiskLevel(str, Enum):
    """Payment risk levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CollectionPriority(str, Enum):
    """Collection action priority."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgingSummary:
    """Aging summary for a client or portfolio."""
    total_outstanding: Decimal
    total_invoices: int
    current_amount: Decimal
    bucket_31_60: Decimal
    bucket_61_90: Decimal
    bucket_91_120: Decimal
    bucket_120_plus: Decimal
    
    @property
    def past_due_amount(self) -> Decimal:
        """Total past due (over 30 days)."""
        return (
            self.bucket_31_60 +
            self.bucket_61_90 +
            self.bucket_91_120 +
            self.bucket_120_plus
        )
    
    @property
    def delinquent_percentage(self) -> float:
        """Percentage of receivables that are delinquent."""
        if self.total_outstanding == 0:
            return 0.0
        return float(self.past_due_amount / self.total_outstanding * 100)


@dataclass
class InvoiceAgingDetail:
    """Detailed aging info for a single invoice."""
    invoice_id: UUID
    invoice_number: str
    client_id: UUID
    client_name: str
    issue_date: date
    due_date: date
    total_amount: Decimal
    paid_amount: Decimal
    outstanding: Decimal
    days_outstanding: int
    days_overdue: int
    aging_bucket: AgingBucket
    status: str
    risk_level: RiskLevel
    last_payment_date: Optional[date] = None
    payment_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ClientPaymentProfile:
    """Payment behavior profile for a client."""
    client_id: UUID
    client_name: str
    total_invoices_issued: int
    total_paid_full: int
    total_paid_partial: int
    total_unpaid: int
    average_days_to_pay: Optional[float] = None
    on_time_payment_rate: float = 0.0
    average_invoice_amount: Decimal = Decimal("0")
    total_lifetime_value: Decimal = Decimal("0")
    risk_level: RiskLevel = RiskLevel.LOW
    credit_recommendation: str = ""
    payment_trend: str = "stable"  # improving, stable, deteriorating


@dataclass
class CollectionAction:
    """Recommended collection action."""
    action_id: str
    action_type: str  # email, call, letter, legal, suspension
    priority: CollectionPriority
    invoice_ids: List[UUID]
    client_id: UUID
    client_name: str
    total_outstanding: Decimal
    recommended_date: date
    suggested_message: str
    escalation_level: int  # 1-4
    expected_outcome: str
    automated: bool


@dataclass
class CollectionStrategy:
    """Comprehensive collection strategy for a client."""
    client_id: UUID
    client_name: str
    total_outstanding: Decimal
    risk_level: RiskLevel
    actions: List[CollectionAction]
    recommended_sequence: List[str]
    timeline_days: int
    expected_collection_rate: float
    notes: str


@dataclass
class PortfolioMetrics:
    """Overall receivables portfolio metrics."""
    total_outstanding: Decimal
    total_invoices: int
    unique_clients: int
    average_dso: float  # Days Sales Outstanding
    aging_summary: AgingSummary
    risk_distribution: Dict[RiskLevel, Decimal]
    collection_rate_30_days: float
    collection_rate_60_days: float
    collection_rate_90_days: float
    trend_direction: str  # improving, stable, deteriorating


@dataclass
class PaymentPrediction:
    """AI prediction for invoice payment."""
    invoice_id: UUID
    prediction_confidence: float  # 0-1
    predicted_payment_date: Optional[date]
    predicted_payment_amount: Decimal
    probability_on_time: float  # 0-1
    probability_late: float
    probability_default: float
    risk_factors: List[str]


# =============================================================
# Invoice Intelligence Agent
# =============================================================

class InvoiceIntelligenceAgent:
    """
    AI agent for intelligent invoice management and collections.
    
    Features:
    - Aging reports with bucket analysis
    - Client payment behavior profiling
    - Predictive payment risk scoring
    - Automated collection strategies
    - Portfolio health monitoring
    - DSO (Days Sales Outstanding) tracking
    
    Aging Buckets:
    - Current: 0-30 days
    - 31-60 days: Early delinquency
    - 61-90 days: Moderate risk
    - 91-120 days: High risk
    - 120+ days: Critical / write-off candidate
    """
    
    # Risk scoring weights
    RISK_WEIGHTS = {
        "days_overdue": 0.40,
        "payment_history": 0.30,
        "invoice_size": 0.15,
        "client_profile": 0.15,
    }
    
    # Aging thresholds
    BUCKETS = [
        (0, 30, AgingBucket.CURRENT),
        (31, 60, AgingBucket.BUCKET_31_60),
        (61, 90, AgingBucket.BUCKET_61_90),
        (91, 120, AgingBucket.BUCKET_91_120),
        (121, 9999, AgingBucket.BUCKET_120_PLUS),
    ]
    
    def __init__(self, db: AsyncSession, current_user: Dict[str, Any]):
        self.db = db
        self.current_user = current_user
        self.cache: Dict[str, Any] = {}
    
    def get_aging_bucket(self, days_overdue: int) -> AgingBucket:
        """Determine aging bucket based on days overdue."""
        for min_days, max_days, bucket in self.BUCKETS:
            if min_days <= days_overdue <= max_days:
                return bucket
        return AgingBucket.BUCKET_120_PLUS
    
    def calculate_risk_level(
        self,
        days_overdue: int,
        outstanding: Decimal,
        client_profile: Optional[ClientPaymentProfile] = None
    ) -> RiskLevel:
        """
        Calculate risk level based on multiple factors.
        """
        score = 0.0
        
        # Days overdue contribution (0-40 points)
        if days_overdue <= 30:
            score += 0
        elif days_overdue <= 60:
            score += 15
        elif days_overdue <= 90:
            score += 25
        elif days_overdue <= 120:
            score += 35
        else:
            score += 40
        
        # Invoice size contribution (0-15 points)
        # Larger invoices are higher risk if overdue
        if outstanding > Decimal("50000"):
            score += 15
        elif outstanding > Decimal("20000"):
            score += 10
        elif outstanding > Decimal("5000"):
            score += 5
        
        # Client history contribution (0-15 points)
        if client_profile:
            if client_profile.risk_level == RiskLevel.HIGH:
                score += 15
            elif client_profile.risk_level == RiskLevel.MEDIUM:
                score += 8
            elif client_profile.payment_trend == "deteriorating":
                score += 10
        
        # Payment history contribution (0-30 points)
        # Assumed neutral if no history available
        score += 15
        
        # Map score to risk level
        if score >= 60:
            return RiskLevel.CRITICAL
        elif score >= 45:
            return RiskLevel.HIGH
        elif score >= 25:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    async def get_outstanding_invoices(
        self,
        client_id: Optional[UUID] = None,
        min_days_overdue: Optional[int] = None,
        max_days_overdue: Optional[int] = None,
        status_filter: Optional[List[str]] = None
    ) -> List[InvoiceAgingDetail]:
        """
        Get all outstanding invoices with aging details.
        """
        query = select(Invoice).where(
            Invoice.status.in_(["unpaid", "partial", "overdue"])
        )
        
        if client_id:
            query = query.where(Invoice.client_id == client_id)
        
        if status_filter:
            query = query.where(Invoice.status.in_(status_filter))
        
        result = await self.db.execute(query)
        invoices = result.scalars().all()
        
        today = date.today()
        aging_details = []
        
        for invoice in invoices:
            # Get client info
            client_result = await self.db.execute(
                select(Client).where(Client.id == invoice.client_id)
            )
            client = client_result.scalar_one_or_none()
            client_name = client.company_name if client else "Unknown"
            
            # Calculate aging
            days_outstanding = (today - invoice.issue_date).days if invoice.issue_date else 0
            
            if invoice.due_date:
                days_overdue = max(0, (today - invoice.due_date).days)
            else:
                # Assume 30 day terms if no due date
                days_overdue = max(0, days_outstanding - 30)
            
            # Filter by overdue range if specified
            if min_days_overdue is not None and days_overdue < min_days_overdue:
                continue
            if max_days_overdue is not None and days_overdue > max_days_overdue:
                continue
            
            outstanding = invoice.outstanding_myr
            
            # Get client profile for risk calculation
            client_profile = await self.get_client_payment_profile(invoice.client_id)
            
            # Calculate risk
            risk_level = self.calculate_risk_level(
                days_overdue=days_overdue,
                outstanding=outstanding,
                client_profile=client_profile
            )
            
            aging_bucket = self.get_aging_bucket(days_overdue)
            
            detail = InvoiceAgingDetail(
                invoice_id=invoice.id,
                invoice_number=invoice.invoice_number or str(invoice.id)[:8],
                client_id=invoice.client_id,
                client_name=client_name,
                issue_date=invoice.issue_date or today,
                due_date=invoice.due_date or (invoice.issue_date + timedelta(days=30)) if invoice.issue_date else today,
                total_amount=invoice.total_myr,
                paid_amount=invoice.paid_amount_myr,
                outstanding=outstanding,
                days_outstanding=days_outstanding,
                days_overdue=days_overdue,
                aging_bucket=aging_bucket,
                status=invoice.status,
                risk_level=risk_level,
            )
            aging_details.append(detail)
        
        # Sort by risk (highest first) then by amount
        aging_details.sort(
            key=lambda x: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(x.risk_level.value, 0),
                x.outstanding
            ),
            reverse=True
        )
        
        return aging_details
    
    async def get_aging_report(
        self,
        client_id: Optional[UUID] = None
    ) -> Tuple[AgingSummary, List[InvoiceAgingDetail]]:
        """
        Generate comprehensive aging report.
        """
        invoices = await self.get_outstanding_invoices(client_id=client_id)
        
        # Calculate bucket totals
        current = Decimal("0")
        bucket_31_60 = Decimal("0")
        bucket_61_90 = Decimal("0")
        bucket_91_120 = Decimal("0")
        bucket_120_plus = Decimal("0")
        
        for inv in invoices:
            if inv.aging_bucket == AgingBucket.CURRENT:
                current += inv.outstanding
            elif inv.aging_bucket == AgingBucket.BUCKET_31_60:
                bucket_31_60 += inv.outstanding
            elif inv.aging_bucket == AgingBucket.BUCKET_61_90:
                bucket_61_90 += inv.outstanding
            elif inv.aging_bucket == AgingBucket.BUCKET_91_120:
                bucket_91_120 += inv.outstanding
            else:
                bucket_120_plus += inv.outstanding
        
        total_outstanding = sum(inv.outstanding for inv in invoices)
        
        summary = AgingSummary(
            total_outstanding=total_outstanding,
            total_invoices=len(invoices),
            current_amount=current,
            bucket_31_60=bucket_31_60,
            bucket_61_90=bucket_61_90,
            bucket_91_120=bucket_91_120,
            bucket_120_plus=bucket_120_plus,
        )
        
        return summary, invoices
    
    async def get_client_payment_profile(
        self,
        client_id: UUID
    ) -> ClientPaymentProfile:
        """
        Analyze client's payment history and behavior.
        """
        # Get all invoices for client
        result = await self.db.execute(
            select(Invoice).where(Invoice.client_id == client_id)
        )
        invoices = result.scalars().all()
        
        # Get client info
        client_result = await self.db.execute(
            select(Client).where(Client.id == client_id)
        )
        client = client_result.scalar_one_or_none()
        client_name = client.company_name if client else "Unknown"
        
        total = len(invoices)
        paid_full = len([i for i in invoices if i.status == "paid"])
        paid_partial = len([i for i in invoices if i.status == "partial"])
        unpaid = len([i for i in invoices if i.status in ["unpaid", "overdue"]])
        
        # Calculate average days to pay
        payment_times = []
        for inv in invoices:
            if inv.status in ["paid", "partial"] and inv.issue_date:
                # This is a simplified calculation
                # In reality, you'd track actual payment dates
                days = 30  # Default assumption
                payment_times.append(days)
        
        avg_days = sum(payment_times) / len(payment_times) if payment_times else None
        
        # Calculate on-time rate
        on_time = len([d for d in payment_times if d <= 30]) if payment_times else 0
        on_time_rate = (on_time / len(payment_times) * 100) if payment_times else 0
        
        # Calculate lifetime value
        total_value = sum(i.total_myr for i in invoices)
        avg_invoice = total_value / total if total > 0 else Decimal("0")
        
        # Determine risk level based on history
        if unpaid > paid_full and total > 3:
            risk_level = RiskLevel.HIGH
        elif on_time_rate < 70 and total > 3:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW
        
        # Payment trend
        if total < 3:
            trend = "insufficient_data"
        elif on_time_rate < 50:
            trend = "deteriorating"
        elif on_time_rate > 85:
            trend = "improving"
        else:
            trend = "stable"
        
        # Credit recommendation
        if risk_level == RiskLevel.LOW and on_time_rate > 90:
            credit_rec = "Increase credit limit; excellent payment history"
        elif risk_level == RiskLevel.HIGH:
            credit_rec = "Require prepayment or deposit; high risk"
        else:
            credit_rec = "Standard credit terms; monitor closely"
        
        return ClientPaymentProfile(
            client_id=client_id,
            client_name=client_name,
            total_invoices_issued=total,
            total_paid_full=paid_full,
            total_paid_partial=paid_partial,
            total_unpaid=unpaid,
            average_days_to_pay=avg_days,
            on_time_payment_rate=on_time_rate,
            average_invoice_amount=avg_invoice,
            total_lifetime_value=total_value,
            risk_level=risk_level,
            credit_recommendation=credit_rec,
            payment_trend=trend,
        )
    
    async def generate_collection_strategy(
        self,
        client_id: UUID
    ) -> CollectionStrategy:
        """
        Generate a tailored collection strategy for a client.
        """
        # Get client profile and outstanding invoices
        profile = await self.get_client_payment_profile(client_id)
        invoices = await self.get_outstanding_invoices(client_id=client_id)
        
        if not invoices:
            return CollectionStrategy(
                client_id=client_id,
                client_name=profile.client_name,
                total_outstanding=Decimal("0"),
                risk_level=RiskLevel.LOW,
                actions=[],
                recommended_sequence=[],
                timeline_days=0,
                expected_collection_rate=100.0,
                notes="No outstanding invoices",
            )
        
        total_outstanding = sum(inv.outstanding for inv in invoices)
        invoice_ids = [inv.invoice_id for inv in invoices]
        
        # Determine risk and priority
        risk_level = profile.risk_level
        
        # Calculate escalation level based on age
        oldest_days = max(inv.days_overdue for inv in invoices)
        if oldest_days > 120:
            escalation = 4
        elif oldest_days > 90:
            escalation = 3
        elif oldest_days > 60:
            escalation = 2
        else:
            escalation = 1
        
        actions = []
        sequence = []
        
        # Build action sequence based on risk
        today = date.today()
        
        if risk_level == RiskLevel.CRITICAL or escalation >= 4:
            # Immediate legal action for critical cases
            actions.append(CollectionAction(
                action_id=f"legal_{client_id}",
                action_type="legal_notice",
                priority=CollectionPriority.URGENT,
                invoice_ids=invoice_ids,
                client_id=client_id,
                client_name=profile.client_name,
                total_outstanding=total_outstanding,
                recommended_date=today,
                suggested_message=f"URGENT: Legal notice required for {total_outstanding:,.2f} MYR outstanding for {len(invoices)} invoices.",
                escalation_level=4,
                expected_outcome="Payment or payment plan within 7 days",
                automated=False,
            ))
            sequence.append("legal_notice")
            timeline_days = 7
            expected_rate = 40.0
            
        elif risk_level == RiskLevel.HIGH or escalation >= 3:
            # Collection call + demand letter
            actions.append(CollectionAction(
                action_id=f"call_{client_id}",
                action_type="collection_call",
                priority=CollectionPriority.HIGH,
                invoice_ids=invoice_ids,
                client_id=client_id,
                client_name=profile.client_name,
                total_outstanding=total_outstanding,
                recommended_date=today,
                suggested_message=f"Priority collection call for {total_outstanding:,.2f} MYR overdue.",
                escalation_level=3,
                expected_outcome="Payment commitment within 3 days",
                automated=False,
            ))
            actions.append(CollectionAction(
                action_id=f"letter_{client_id}",
                action_type="demand_letter",
                priority=CollectionPriority.HIGH,
                invoice_ids=invoice_ids,
                client_id=client_id,
                client_name=profile.client_name,
                total_outstanding=total_outstanding,
                recommended_date=today + timedelta(days=2),
                suggested_message=f"Formal demand letter for overdue payment.",
                escalation_level=3,
                expected_outcome="Payment within 14 days",
                automated=True,
            ))
            sequence = ["collection_call", "demand_letter"]
            timeline_days = 14
            expected_rate = 65.0
            
        elif risk_level == RiskLevel.MEDIUM or escalation >= 2:
            # Email reminder + follow-up call
            actions.append(CollectionAction(
                action_id=f"email_{client_id}",
                action_type="email_reminder",
                priority=CollectionPriority.MEDIUM,
                invoice_ids=invoice_ids,
                client_id=client_id,
                client_name=profile.client_name,
                total_outstanding=total_outstanding,
                recommended_date=today,
                suggested_message=f"Friendly reminder: {total_outstanding:,.2f} MYR overdue. Please arrange payment.",
                escalation_level=2,
                expected_outcome="Payment within 21 days",
                automated=True,
            ))
            actions.append(CollectionAction(
                action_id=f"call_{client_id}",
                action_type="followup_call",
                priority=CollectionPriority.MEDIUM,
                invoice_ids=invoice_ids,
                client_id=client_id,
                client_name=profile.client_name,
                total_outstanding=total_outstanding,
                recommended_date=today + timedelta(days=7),
                suggested_message=f"Follow-up call for overdue payment.",
                escalation_level=2,
                expected_outcome="Payment commitment",
                automated=False,
            ))
            sequence = ["email_reminder", "followup_call"]
            timeline_days = 21
            expected_rate = 80.0
            
        else:
            # Standard email reminder
            actions.append(CollectionAction(
                action_id=f"email_{client_id}",
                action_type="email_reminder",
                priority=CollectionPriority.LOW,
                invoice_ids=invoice_ids,
                client_id=client_id,
                client_name=profile.client_name,
                total_outstanding=total_outstanding,
                recommended_date=today,
                suggested_message=f"Gentle reminder: Invoice payment due. Outstanding: {total_outstanding:,.2f} MYR",
                escalation_level=1,
                expected_outcome="Payment within 30 days",
                automated=True,
            ))
            sequence = ["email_reminder"]
            timeline_days = 30
            expected_rate = 90.0
        
        # Build notes
        notes = f"""
        Collection strategy for {profile.client_name}:
        - Outstanding: {total_outstanding:,.2f} MYR across {len(invoices)} invoices
        - Risk Level: {risk_level.value.upper()}
        - Payment Trend: {profile.payment_trend}
        - On-time Rate: {profile.on_time_payment_rate:.1f}%
        - Recommended Timeline: {timeline_days} days
        - Expected Collection Rate: {expected_rate:.1f}%
        
        {profile.credit_recommendation}
        """.strip()
        
        return CollectionStrategy(
            client_id=client_id,
            client_name=profile.client_name,
            total_outstanding=total_outstanding,
            risk_level=risk_level,
            actions=actions,
            recommended_sequence=sequence,
            timeline_days=timeline_days,
            expected_collection_rate=expected_rate,
            notes=notes,
        )
    
    async def get_portfolio_metrics(self) -> PortfolioMetrics:
        """
        Calculate overall receivables portfolio metrics.
        """
        # Get all outstanding invoices
        invoices = await self.get_outstanding_invoices()
        
        summary, _ = await self.get_aging_report()
        
        # Calculate DSO
        total_outstanding = summary.total_outstanding
        if total_outstanding > 0:
            weighted_days = sum(
                inv.days_outstanding * float(inv.outstanding)
                for inv in invoices
            )
            dso = weighted_days / float(total_outstanding)
        else:
            dso = 0.0
        
        # Risk distribution
        risk_dist = {
            RiskLevel.LOW: Decimal("0"),
            RiskLevel.MEDIUM: Decimal("0"),
            RiskLevel.HIGH: Decimal("0"),
            RiskLevel.CRITICAL: Decimal("0"),
        }
        for inv in invoices:
            risk_dist[inv.risk_level] += inv.outstanding
        
        # Count unique clients
        unique_clients = len(set(inv.client_id for inv in invoices))
        
        # Trend (would use historical data in production)
        trend = "stable"
        
        return PortfolioMetrics(
            total_outstanding=total_outstanding,
            total_invoices=len(invoices),
            unique_clients=unique_clients,
            average_dso=dso,
            aging_summary=summary,
            risk_distribution=risk_dist,
            collection_rate_30_days=90.0,  # Placeholder
            collection_rate_60_days=75.0,
            collection_rate_90_days=60.0,
            trend_direction=trend,
        )
    
    async def predict_payment(
        self,
        invoice_id: UUID
    ) -> PaymentPrediction:
        """
        Predict when and how much an invoice will be paid.
        """
        # Get invoice details
        result = await self.db.execute(
            select(Invoice).where(Invoice.id == invoice_id)
        )
        invoice = result.scalar_one_or_none()
        
        if not invoice:
            return PaymentPrediction(
                invoice_id=invoice_id,
                prediction_confidence=0.0,
                predicted_payment_date=None,
                predicted_payment_amount=Decimal("0"),
                probability_on_time=0.0,
                probability_late=0.0,
                probability_default=1.0,
                risk_factors=["Invoice not found"],
            )
        
        # Get client profile
        profile = await self.get_client_payment_profile(invoice.client_id)
        
        today = date.today()
        
        if invoice.due_date:
            days_to_due = (invoice.due_date - today).days
            days_overdue = max(0, -days_to_due)
        else:
            days_overdue = 0
            days_to_due = 30
        
        # Base prediction on client profile
        on_time_rate = profile.on_time_payment_rate / 100
        avg_days = profile.average_days_to_pay or 30
        
        # Adjust for current invoice age
        if days_overdue > 90:
            prob_on_time = 0.05
            prob_late = 0.15
            prob_default = 0.80
        elif days_overdue > 60:
            prob_on_time = 0.15
            prob_late = 0.35
            prob_default = 0.50
        elif days_overdue > 30:
            prob_on_time = 0.30
            prob_late = 0.50
            prob_default = 0.20
        elif days_overdue > 0:
            prob_on_time = 0.50
            prob_late = 0.40
            prob_default = 0.10
        else:
            # Not yet due
            prob_on_time = max(0.3, on_time_rate)
            prob_late = 0.30
            prob_default = 0.05
        
        # Predict payment date
        if prob_on_time > prob_late:
            if invoice.due_date and days_to_due > 0:
                predicted_date = invoice.due_date - timedelta(days=2)
            else:
                predicted_date = today + timedelta(days=5)
        elif prob_late > prob_default:
            predicted_date = today + timedelta(days=avg_days + 15)
        else:
            predicted_date = None  # Default predicted
        
        # Risk factors
        risk_factors = []
        if profile.risk_level == RiskLevel.HIGH:
            risk_factors.append("Client has high risk profile")
        if profile.payment_trend == "deteriorating":
            risk_factors.append("Payment trend is deteriorating")
        if invoice.outstanding_myr > Decimal("20000"):
            risk_factors.append("Large invoice amount")
        if days_overdue > 60:
            risk_factors.append("Significantly overdue")
        
        return PaymentPrediction(
            invoice_id=invoice_id,
            prediction_confidence=0.75,
            predicted_payment_date=predicted_date,
            predicted_payment_amount=invoice.outstanding_myr,
            probability_on_time=prob_on_time,
            probability_late=prob_late,
            probability_default=prob_default,
            risk_factors=risk_factors if risk_factors else ["No significant risk factors"],
        )


# =============================================================
# Pydantic Models for API
# =============================================================

class AgingReportRequest(BaseModel):
    """Request for aging report."""
    client_id: Optional[str] = None
    include_details: bool = True


class AgingReportResponse(BaseModel):
    """Aging report response."""
    total_outstanding: float
    total_invoices: int
    current_amount: float
    bucket_31_60: float
    bucket_61_90: float
    bucket_91_120: float
    bucket_120_plus: float
    past_due_amount: float
    delinquent_percentage: float
    invoice_details: List[Dict[str, Any]] = []


class ClientProfileRequest(BaseModel):
    """Request for client payment profile."""
    client_id: str


class ClientProfileResponse(BaseModel):
    """Client payment profile response."""
    client_id: str
    client_name: str
    total_invoices_issued: int
    total_paid_full: int
    total_paid_partial: int
    total_unpaid: int
    average_days_to_pay: Optional[float]
    on_time_payment_rate: float
    average_invoice_amount: float
    total_lifetime_value: float
    risk_level: str
    credit_recommendation: str
    payment_trend: str


class CollectionStrategyRequest(BaseModel):
    """Request for collection strategy."""
    client_id: str


class CollectionActionResponse(BaseModel):
    """Collection action response."""
    action_id: str
    action_type: str
    priority: str
    invoice_ids: List[str]
    client_name: str
    total_outstanding: float
    recommended_date: str
    suggested_message: str
    escalation_level: int
    expected_outcome: str
    automated: bool


class CollectionStrategyResponse(BaseModel):
    """Collection strategy response."""
    client_id: str
    client_name: str
    total_outstanding: float
    risk_level: str
    actions: List[CollectionActionResponse]
    recommended_sequence: List[str]
    timeline_days: int
    expected_collection_rate: float
    notes: str


class PortfolioMetricsResponse(BaseModel):
    """Portfolio metrics response."""
    total_outstanding: float
    total_invoices: int
    unique_clients: int
    average_dso: float
    current_amount: float
    past_due_30_60: float
    past_due_60_90: float
    past_due_90_plus: float
    risk_low: float
    risk_medium: float
    risk_high: float
    risk_critical: float
    trend_direction: str


class PaymentPredictionRequest(BaseModel):
    """Request for payment prediction."""
    invoice_id: str


class PaymentPredictionResponse(BaseModel):
    """Payment prediction response."""
    invoice_id: str
    prediction_confidence: float
    predicted_payment_date: Optional[str]
    predicted_payment_amount: float
    probability_on_time: float
    probability_late: float
    probability_default: float
    risk_factors: List[str]


class CollectionPromptRequest(BaseModel):
    """Request for collection prompt message."""
    client_id: str
    tone: str = Field(default="professional", description="professional, friendly, firm, urgent")


class CollectionPromptResponse(BaseModel):
    """Collection prompt response."""
    client_id: str
    client_name: str
    outstanding_amount: float
    invoice_count: int
    suggested_message: str
    subject_line: str
    call_script: str
    urgency_level: str
    recommended_action: str
