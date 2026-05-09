# =============================================================
# Hi-Tech Waste Management — Bulk Import Agent
# AI-powered CSV/Excel bulk data import with validation
# =============================================================

from __future__ import annotations

import csv
import io
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union, Callable

from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from agents.database_agent import DatabaseAgent, DatabaseAction, DatabaseOperationRequest, EntityType, ENTITY_METADATA
from models.client import ClientCreate, ClientWasteStreamCreate
from models.job import JobCreate, RecurringJobTemplateCreate
from models.vehicle import VehicleCreate, TripCreate
from models.user import UserCreate
from models.scheduled_waste import ScheduledWasteBatchCreate
from models.esg import CarbonRecordCreate
from models.recyclable import RecyclableRecordCreate
from models.equipment import ContainerCreate, CompactionMachineCreate
from models.bsf import BSFBatchCreate
from models.destruction import DestructionJobCreate

logger = logging.getLogger(__name__)


# =============================================================
# Import Result Models
# =============================================================

class ImportStatus(str, Enum):
    PENDING = "pending"
    VALIDATING = "validating"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class RowError:
    """Error for a specific row in the import."""
    row_number: int
    row_data: Dict[str, Any]
    error_message: str
    field_errors: Dict[str, str] = field(default_factory=dict)


@dataclass
class ImportResult:
    """Result of a bulk import operation."""
    import_id: str
    entity_type: EntityType
    status: ImportStatus
    total_rows: int = 0
    successful_rows: int = 0
    failed_rows: int = 0
    created_ids: List[str] = field(default_factory=list)
    errors: List[RowError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    summary: str = ""
    processing_time_seconds: float = 0.0


@dataclass
class ColumnMapping:
    """Mapping of file columns to entity fields."""
    file_column: str
    entity_field: str
    transform_func: Optional[Callable[[Any], Any]] = None
    required: bool = False


# =============================================================
# Entity Field Mappings
# =============================================================

# Standard column name variations mapped to entity fields
COLUMN_ALIASES: Dict[str, List[str]] = {
    # Client fields
    "company_name": ["company name", "company", "client name", "client", "organization", "org name"],
    "pic_name": ["pic name", "person in charge", "contact person", "contact name", "primary contact"],
    "pic_email": ["pic email", "email", "contact email", "email address"],
    "pic_phone": ["pic phone", "phone", "contact phone", "telephone", "mobile"],
    "ssm_number": ["ssm", "ssm number", "company reg no", "registration number", "biz reg"],
    "billing_address": ["billing address", "address", "company address", "invoice address"],
    "industry_vertical": ["industry", "sector", "industry type", "business type"],
    "contract_start_date": ["contract start", "start date", "contract from", "agreement start"],
    "contract_end_date": ["contract end", "end date", "contract to", "agreement end"],
    "payment_terms_days": ["payment terms", "terms", "credit days", "payment days"],
    
    # Job fields
    "job_type": ["job type", "service type", "waste type", "collection type"],
    "scheduled_date": ["scheduled date", "collection date", "service date", "date"],
    "site_address": ["site address", "collection address", "location", "site"],
    "quantity_kg": ["quantity", "weight", "amount", "kg", "tonnage"],
    "frequency": ["frequency", "recurrence", "schedule"],
    
    # Vehicle fields
    "registration": ["registration", "plate number", "plate", "vehicle no", "license plate"],
    "vehicle_type": ["vehicle type", "type", "category", "class"],
    "make": ["make", "manufacturer", "brand"],
    "model": ["model", "model name"],
    "year": ["year", "manufacturing year", "model year"],
    "capacity_kg": ["capacity", "load capacity", "max weight"],
    
    # User fields
    "full_name": ["full name", "name", "employee name", "staff name"],
    "email": ["email", "email address", "work email"],
    "role": ["role", "position", "job title", "designation"],
    "department": ["department", "division", "team"],
    "employee_id": ["employee id", "staff id", "emp no"],
    
    # Equipment fields
    "container_number": ["container no", "container number", "skip no", "bin id"],
    "container_type": ["container type", "skip type", "bin type"],
    "size_yards": ["size", "capacity", "yards", "cubic yards"],
    "location": ["location", "deployment location", "site"],
    "client_id": ["client id", "client", "customer id"],
    
    # Common
    "status": ["status", "state", "condition"],
    "notes": ["notes", "remarks", "comments", "description"],
    "created_at": ["created", "created date", "entry date"],
}


def normalize_column_name(name: str) -> str:
    """Normalize column name for matching."""
    return name.lower().strip().replace('_', ' ').replace('-', ' ')


def find_entity_field(column_name: str) -> Optional[str]:
    """Find entity field name from column alias."""
    normalized = normalize_column_name(column_name)
    for field_name, aliases in COLUMN_ALIASES.items():
        if normalized in aliases or normalized == field_name.replace('_', ' '):
            return field_name
    return None


# =============================================================
# Field Transformers
# =============================================================

class FieldTransformers:
    """Common field transformation functions."""
    
    @staticmethod
    def to_uuid(value: Any) -> Optional[uuid.UUID]:
        """Convert string to UUID."""
        if not value:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except ValueError:
            return None
    
    @staticmethod
    def to_date(value: Any) -> Optional[date]:
        """Convert various date formats to date object."""
        if not value:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        
        date_str = str(value).strip()
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%Y/%m/%d",
            "%d.%m.%Y",
            "%b %d, %Y",
            "%B %d, %Y",
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        return None
    
    @staticmethod
    def to_decimal(value: Any) -> Optional[Decimal]:
        """Convert value to Decimal."""
        if not value:
            return None
        if isinstance(value, Decimal):
            return value
        try:
            # Remove common formatting
            cleaned = str(value).replace(',', '').replace('$', '').replace('RM', '').strip()
            return Decimal(cleaned)
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def to_int(value: Any) -> Optional[int]:
        """Convert value to int."""
        if not value:
            return None
        if isinstance(value, int):
            return value
        try:
            cleaned = str(value).replace(',', '').strip()
            return int(float(cleaned))
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def to_bool(value: Any) -> Optional[bool]:
        """Convert value to boolean."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        
        true_values = ['yes', 'true', '1', 'y', 'active', 'enabled', 'on']
        false_values = ['no', 'false', '0', 'n', 'inactive', 'disabled', 'off']
        
        normalized = str(value).lower().strip()
        if normalized in true_values:
            return True
        if normalized in false_values:
            return False
        return None
    
    @staticmethod
    def clean_string(value: Any) -> Optional[str]:
        """Clean and validate string."""
        if not value:
            return None
        cleaned = str(value).strip()
        return cleaned if cleaned else None


# Field type transformers mapping
FIELD_TRANSFORMERS: Dict[str, Callable] = {
    "client_id": FieldTransformers.to_uuid,
    "user_id": FieldTransformers.to_uuid,
    "job_id": FieldTransformers.to_uuid,
    "vehicle_id": FieldTransformers.to_uuid,
    "scheduled_date": FieldTransformers.to_date,
    "contract_start_date": FieldTransformers.to_date,
    "contract_end_date": FieldTransformers.to_date,
    "intake_date": FieldTransformers.to_date,
    "service_date": FieldTransformers.to_date,
    "quantity_kg": FieldTransformers.to_decimal,
    "weight_kg": FieldTransformers.to_decimal,
    "capacity_kg": FieldTransformers.to_decimal,
    "size_yards": FieldTransformers.to_decimal,
    "payment_terms_days": FieldTransformers.to_int,
    "year": FieldTransformers.to_int,
    "is_active": FieldTransformers.to_bool,
}


# =============================================================
# Bulk Import Agent
# =============================================================

class BulkImportAgent:
    """
    AI agent for bulk importing data from CSV/Excel files.
    
    Features:
    - Automatic column mapping
    - Data validation using Pydantic schemas
    - Error reporting with row-level details
    - Partial import support (continue on errors)
    - Progress tracking
    """
    
    def __init__(self, db: AsyncSession, current_user: Dict[str, Any]):
        self.db = db
        self.current_user = current_user
        self.db_agent = DatabaseAgent(db, current_user)
    
    async def parse_file(
        self,
        file_content: bytes,
        filename: str,
        entity_type: EntityType
    ) -> List[Dict[str, Any]]:
        """Parse CSV or Excel file into list of row dictionaries."""
        file_ext = filename.lower().split('.')[-1]
        
        if file_ext == 'csv':
            return await self._parse_csv(file_content)
        elif file_ext in ['xlsx', 'xls']:
            return await self._parse_excel(file_content)
        else:
            raise ValueError(f"Unsupported file format: {file_ext}. Use CSV or Excel.")
    
    async def _parse_csv(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse CSV content."""
        # Try different encodings
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
        
        for encoding in encodings:
            try:
                text = content.decode(encoding)
                reader = csv.DictReader(io.StringIO(text))
                rows = []
                for row in reader:
                    # Clean up keys and values
                    cleaned = {
                        k.strip(): v.strip() if v else None
                        for k, v in row.items()
                        if k and k.strip()
                    }
                    if any(v for v in cleaned.values() if v):  # Skip empty rows
                        rows.append(cleaned)
                return rows
            except UnicodeDecodeError:
                continue
        
        raise ValueError("Could not decode CSV file - unsupported encoding")
    
    async def _parse_excel(self, content: bytes) -> List[Dict[str, Any]]:
        """Parse Excel content using openpyxl or pandas."""
        try:
            import pandas as pd
            
            df = pd.read_excel(io.BytesIO(content))
            # Convert to list of dicts, handling NaN values
            rows = []
            for _, row in df.iterrows():
                row_dict = {}
                for col, val in row.items():
                    if pd.notna(val):
                        row_dict[str(col)] = str(val)
                    else:
                        row_dict[str(col)] = None
                if any(v for v in row_dict.values() if v):
                    rows.append(row_dict)
            return rows
        except ImportError:
            raise ImportError(
                "Excel parsing requires pandas. "
                "Install with: pip install pandas openpyxl"
            )
    
    def auto_map_columns(
        self,
        columns: List[str],
        entity_type: EntityType
    ) -> Dict[str, ColumnMapping]:
        """
        Automatically map file columns to entity fields.
        Returns dict of file_column -> ColumnMapping.
        """
        mappings = {}
        
        # Get entity metadata
        meta = ENTITY_METADATA.get(entity_type, {})
        required_fields = meta.get("required_fields", [])
        create_schema = meta.get("create_schema")
        
        # Get all available fields from schema
        available_fields = set()
        if create_schema:
            schema = create_schema.model_json_schema()
            available_fields = set(schema.get("properties", {}).keys())
        
        for col in columns:
            entity_field = find_entity_field(col)
            if entity_field and entity_field in available_fields:
                # Determine transformer based on field type
                transform_func = FIELD_TRANSFORMERS.get(entity_field)
                
                mappings[col] = ColumnMapping(
                    file_column=col,
                    entity_field=entity_field,
                    transform_func=transform_func,
                    required=entity_field in required_fields
                )
        
        return mappings
    
    async def validate_and_import(
        self,
        rows: List[Dict[str, Any]],
        entity_type: EntityType,
        column_mappings: Optional[Dict[str, ColumnMapping]] = None,
        skip_errors: bool = True,
        dry_run: bool = False
    ) -> ImportResult:
        """
        Validate and import rows into the database.
        
        Args:
            rows: List of row dictionaries from parsed file
            entity_type: Type of entity to create
            column_mappings: Optional explicit column mappings
            skip_errors: If True, continue importing on row errors
            dry_run: If True, validate only without creating
        
        Returns:
            ImportResult with details of success/failures
        """
        import_id = str(uuid.uuid4())
        start_time = datetime.now()
        
        if not rows:
            return ImportResult(
                import_id=import_id,
                entity_type=entity_type,
                status=ImportStatus.FAILED,
                total_rows=0,
                summary="No data rows found in file"
            )
        
        # Auto-generate column mappings if not provided
        if not column_mappings:
            columns = list(rows[0].keys())
            column_mappings = self.auto_map_columns(columns, entity_type)
        
        # Check for missing required field mappings
        meta = ENTITY_METADATA.get(entity_type, {})
        required_fields = meta.get("required_fields", [])
        mapped_fields = {m.entity_field for m in column_mappings.values()}
        missing_required = set(required_fields) - mapped_fields
        
        if missing_required:
            return ImportResult(
                import_id=import_id,
                entity_type=entity_type,
                status=ImportStatus.FAILED,
                total_rows=len(rows),
                summary=f"Missing required column mappings: {', '.join(missing_required)}. "
                       f"Please ensure your file has columns for these fields."
            )
        
        result = ImportResult(
            import_id=import_id,
            entity_type=entity_type,
            status=ImportStatus.VALIDATING,
            total_rows=len(rows)
        )
        
        # Get create schema
        create_schema = meta.get("create_schema")
        if not create_schema:
            result.status = ImportStatus.FAILED
            result.summary = f"Import not supported for {entity_type.value}"
            return result
        
        # Process each row
        validated_rows = []
        
        for idx, row in enumerate(rows, start=1):
            try:
                # Transform row data using mappings
                transformed_data = self._transform_row(row, column_mappings)
                
                # Validate using Pydantic schema
                validated = create_schema(**transformed_data)
                validated_rows.append((idx, row, validated))
                
            except ValidationError as e:
                field_errors = {}
                for error in e.errors():
                    field = '.'.join(str(x) for x in error['loc'])
                    field_errors[field] = error['msg']
                
                result.errors.append(RowError(
                    row_number=idx,
                    row_data=row,
                    error_message=str(e),
                    field_errors=field_errors
                ))
                result.failed_rows += 1
                
                if not skip_errors:
                    result.status = ImportStatus.FAILED
                    break
                    
            except Exception as e:
                result.errors.append(RowError(
                    row_number=idx,
                    row_data=row,
                    error_message=str(e)
                ))
                result.failed_rows += 1
                
                if not skip_errors:
                    result.status = ImportStatus.FAILED
                    break
        
        if result.status == ImportStatus.FAILED and not skip_errors:
            result.summary = f"Import failed at row {result.failed_rows}. Fix errors and retry."
            result.processing_time_seconds = (datetime.now() - start_time).total_seconds()
            return result
        
        # Dry run - just return validation results
        if dry_run:
            result.status = ImportStatus.COMPLETED if result.failed_rows == 0 else ImportStatus.PARTIAL
            result.summary = (
                f"Dry run complete: {len(validated_rows)} rows valid, "
                f"{result.failed_rows} rows have errors"
            )
            result.processing_time_seconds = (datetime.now() - start_time).total_seconds()
            return result
        
        # Import validated rows
        result.status = ImportStatus.IMPORTING
        
        for idx, original_row, validated_data in validated_rows:
            try:
                request = DatabaseOperationRequest(
                    action=DatabaseAction.CREATE,
                    entity_type=entity_type,
                    data=validated_data.model_dump()
                )
                
                operation_result = await self.db_agent.execute_operation(request)
                
                if operation_result.success:
                    result.successful_rows += 1
                    if operation_result.metadata and operation_result.metadata.get("id"):
                        result.created_ids.append(str(operation_result.metadata["id"]))
                else:
                    result.failed_rows += 1
                    result.errors.append(RowError(
                        row_number=idx,
                        row_data=original_row,
                        error_message=operation_result.message or operation_result.error or "Unknown error"
                    ))
                    
                    if not skip_errors:
                        result.status = ImportStatus.PARTIAL
                        break
                        
            except Exception as e:
                result.failed_rows += 1
                result.errors.append(RowError(
                    row_number=idx,
                    row_data=original_row,
                    error_message=str(e)
                ))
                
                if not skip_errors:
                    result.status = ImportStatus.PARTIAL
                    break
        
        # Determine final status
        if result.failed_rows == 0:
            result.status = ImportStatus.COMPLETED
        elif result.successful_rows > 0:
            result.status = ImportStatus.PARTIAL
        else:
            result.status = ImportStatus.FAILED
        
        # Generate summary
        result.summary = (
            f"Import {result.status.value}: "
            f"{result.successful_rows} created, "
            f"{result.failed_rows} failed, "
            f"{result.total_rows} total"
        )
        
        result.processing_time_seconds = (datetime.now() - start_time).total_seconds()
        
        return result
    
    def _transform_row(
        self,
        row: Dict[str, Any],
        mappings: Dict[str, ColumnMapping]
    ) -> Dict[str, Any]:
        """Transform a row using column mappings."""
        result = {}
        
        for file_col, mapping in mappings.items():
            value = row.get(file_col)
            
            if value is not None and value != '':
                if mapping.transform_func:
                    value = mapping.transform_func(value)
                else:
                    value = FieldTransformers.clean_string(value)
                
                if value is not None:
                    result[mapping.entity_field] = value
        
        return result
    
    def suggest_column_mappings(
        self,
        columns: List[str],
        entity_type: EntityType
    ) -> Dict[str, str]:
        """
        Suggest column mappings and return as display-friendly dict.
        """
        mappings = self.auto_map_columns(columns, entity_type)
        
        suggestions = {}
        for col in columns:
            if col in mappings:
                suggestions[col] = mappings[col].entity_field
            else:
                suggestions[col] = "(not matched)"
        
        return suggestions
    
    def get_import_template(self, entity_type: EntityType) -> List[str]:
        """
        Get a list of recommended column names for an entity type.
        """
        meta = ENTITY_METADATA.get(entity_type, {})
        required = meta.get("required_fields", [])
        create_schema = meta.get("create_schema")
        
        if not create_schema:
            return []
        
        schema = create_schema.model_json_schema()
        properties = schema.get("properties", {})
        
        # Build template with examples
        template = []
        for field_name, field_info in properties.items():
            if field_name == "waste_streams":
                continue
            
            is_required = field_name in required
            field_type = field_info.get("type", "string")
            
            # Find friendly column name
            friendly_name = field_name.replace('_', ' ').title()
            for alias in COLUMN_ALIASES.get(field_name, []):
                if alias != field_name.replace('_', ' '):
                    friendly_name = alias.title()
                    break
            
            marker = "*" if is_required else ""
            template.append(f"{friendly_name}{marker}")
        
        return template


# =============================================================
# Pydantic Models for API
# =============================================================

class BulkImportRequest(BaseModel):
    """Request for bulk import."""
    entity_type: EntityType
    file_content_base64: str  # Base64 encoded file
    filename: str
    column_mappings: Optional[Dict[str, str]] = None  # Optional explicit mappings
    skip_errors: bool = True
    dry_run: bool = False


class BulkImportResponse(BaseModel):
    """Response from bulk import."""
    import_id: str
    entity_type: str
    status: str
    total_rows: int
    successful_rows: int
    failed_rows: int
    created_count: int
    errors: List[Dict[str, Any]]
    warnings: List[str]
    summary: str
    processing_time_seconds: float
    suggested_mappings: Optional[Dict[str, str]] = None


class ImportPreviewRequest(BaseModel):
    """Request to preview import without executing."""
    entity_type: EntityType
    file_content_base64: str
    filename: str


class ImportPreviewResponse(BaseModel):
    """Preview of what would be imported."""
    entity_type: str
    total_rows: int
    detected_columns: List[str]
    suggested_mappings: Dict[str, str]
    sample_transformed: List[Dict[str, Any]]  # First 3 rows transformed
    missing_required_fields: List[str]
    can_import: bool


class ImportTemplateResponse(BaseModel):
    """Template for a specific entity type."""
    entity_type: str
    required_columns: List[str]
    optional_columns: List[str]
    example_csv: str  # Sample CSV content
