#!/usr/bin/env python3
"""
Hi-Tech Waste Management - Database Seed Script
Populates the database with realistic Malaysian waste management sample data.

Usage:
    cd backend
    python ../scripts/seed_db.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/backend")

# When running locally (outside Docker), override service hostnames to localhost
# so the script can reach the Docker-exposed ports directly.
_local_overrides = {
    "DATABASE_URL": "postgresql://hitech:password@localhost:5432/hitech_waste",
    "REDIS_URL":    "redis://localhost:6379",
    "MILVUS_HOST":  "localhost",
}
for k, v in _local_overrides.items():
    os.environ.setdefault(k, v)
# Force localhost even if .env already set the Docker service name
for k, v in _local_overrides.items():
    os.environ[k] = v

import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import text
from database import AsyncSessionLocal
from passlib.context import CryptContext
import models  # registers all ORM models with Base.metadata

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── Sample data ────────────────────────────────────────────────────────────

USERS = [
    {"email": "admin@hitechwaste.com.my",      "full_name": "Ahmad Razali bin Hassan",    "role": "superadmin",         "password": "Admin@1234"},
    {"email": "ops@hitechwaste.com.my",        "full_name": "Nurul Ain binti Yusof",      "role": "operations_manager", "password": "Ops@1234"},
    {"email": "compliance@hitechwaste.com.my", "full_name": "Mohd Faizal bin Othman",     "role": "compliance_officer", "password": "Comp@1234"},
    {"email": "driver1@hitechwaste.com.my",    "full_name": "Rajan a/l Krishnamurthy",    "role": "driver",             "password": "Driver@1234"},
    {"email": "driver2@hitechwaste.com.my",    "full_name": "Lim Wei Kang",               "role": "driver",             "password": "Driver@1234"},
    {"email": "driver3@hitechwaste.com.my",    "full_name": "Ahmed bin Hassan",          "role": "driver",             "password": "Driver@1234"},
    {"email": "driver4@hitechwaste.com.my",    "full_name": "Vijay Kumar a/l Raman",     "role": "driver",             "password": "Driver@1234"},
    {"email": "supervisor@hitechwaste.com.my", "full_name": "Siti Hajar binti Mahmud",    "role": "field_supervisor",   "password": "Sup@1234"},
    {"email": "finance@hitechwaste.com.my",    "full_name": "Tan Bee Lian",               "role": "management",         "password": "Fin@1234"},
    {"email": "portal@unilever.com.my",        "full_name": "James Wong",                 "role": "client",             "password": "Client@1234"},
]

CLIENTS = [
    {
        "company_name": "Unilever Malaysia Holdings Sdn Bhd",
        "industry_vertical": "FMCG / Manufacturing",
        "ssm_number": "199001012345",
        "address": "Jalan Tandang, Petaling Jaya",
        "city": "Petaling Jaya", "state": "Selangor",
        "pic_name": "James Wong", "pic_email": "portal@unilever.com.my", "pic_phone": "+60123456789",
        "contract_start": date(2024, 1, 1), "contract_end": date(2026, 12, 31),
        "sla_diversion_target": Decimal("75.00"), "billing_model": "tonnage",
    },
    {
        "company_name": "Nestle Malaysia Berhad",
        "industry_vertical": "Food & Beverage",
        "ssm_number": "199001023456",
        "address": "Jalan Damansara, Petaling Jaya",
        "city": "Petaling Jaya", "state": "Selangor",
        "pic_name": "Priya Nair", "pic_email": "priya.nair@nestle.com.my", "pic_phone": "+60123456790",
        "contract_start": date(2024, 3, 1), "contract_end": date(2026, 2, 28),
        "sla_diversion_target": Decimal("70.00"), "billing_model": "tonnage",
    },
    {
        "company_name": "KPJ Damansara Specialist Hospital",
        "industry_vertical": "Healthcare",
        "ssm_number": "199001034567",
        "address": "Jalan Damansara, Damansara Utama",
        "city": "Petaling Jaya", "state": "Selangor",
        "pic_name": "Dr. Azman bin Ismail", "pic_email": "azman@kpj.com.my", "pic_phone": "+60123456791",
        "contract_start": date(2024, 6, 1), "contract_end": date(2025, 5, 31),
        "sla_diversion_target": Decimal("40.00"), "billing_model": "trip",
    },
    {
        "company_name": "Petronas Research Sdn Bhd",
        "industry_vertical": "Oil & Gas",
        "ssm_number": "199001045678",
        "address": "Jalan Semantan, Damansara Heights",
        "city": "Kuala Lumpur", "state": "Wilayah Persekutuan",
        "pic_name": "Hafizuddin bin Zainudin", "pic_email": "hafiz@petronas.com.my", "pic_phone": "+60123456792",
        "contract_start": date(2023, 7, 1), "contract_end": date(2025, 6, 30),
        "sla_diversion_target": Decimal("60.00"), "billing_model": "lumpsum",
    },
    {
        "company_name": "Top Glove Corporation Berhad",
        "industry_vertical": "Manufacturing / Rubber",
        "ssm_number": "199001056789",
        "address": "Jalan Meru, Klang",
        "city": "Klang", "state": "Selangor",
        "pic_name": "Lee Siew Ling", "pic_email": "siewling@topglove.com.my", "pic_phone": "+60123456793",
        "contract_start": date(2024, 1, 15), "contract_end": date(2026, 1, 14),
        "sla_diversion_target": Decimal("65.00"), "billing_model": "tonnage",
    },
    {
        "company_name": "Intel Malaysia Sdn Bhd",
        "industry_vertical": "Electronics / Semiconductor",
        "ssm_number": "199001067890",
        "address": "Jalan Hi-Tech 2/3, Kulim Hi-Tech Park",
        "city": "Kulim", "state": "Kedah",
        "pic_name": "David Chen", "pic_email": "david.chen@intel.com", "pic_phone": "+60123456794",
        "contract_start": date(2023, 9, 1), "contract_end": date(2025, 8, 31),
        "sla_diversion_target": Decimal("80.00"), "billing_model": "tonnage",
    },
    {
        "company_name": "Malaysia Airports Holdings Berhad",
        "industry_vertical": "Aviation / Transportation",
        "ssm_number": "199001078901",
        "address": "Kuala Lumpur International Airport, Sepang",
        "city": "Sepang", "state": "Selangor",
        "pic_name": "Noraini binti Abdullah", "pic_email": "noraini@malaysiaairports.com.my", "pic_phone": "+60123456795",
        "contract_start": date(2024, 1, 1), "contract_end": date(2026, 12, 31),
        "sla_diversion_target": Decimal("55.00"), "billing_model": "lumpsum",
    },
    {
        "company_name": "Sunway Group Berhad",
        "industry_vertical": "Property / Construction",
        "ssm_number": "199001089012",
        "address": "Persiaran Lagoon, Bandar Sunway",
        "city": "Subang Jaya", "state": "Selangor",
        "pic_name": "Jeffrey Cheah Jr.", "pic_email": "jeffrey@sunway.com.my", "pic_phone": "+60123456796",
        "contract_start": date(2024, 2, 1), "contract_end": date(2026, 1, 31),
        "sla_diversion_target": Decimal("70.00"), "billing_model": "tonnage",
    },
    {
        "company_name": "Mah Sing Group Berhad",
        "industry_vertical": "Property / Construction",
        "ssm_number": "199001090123",
        "address": "Jalan Sungai Besi, Kuala Lumpur",
        "city": "Kuala Lumpur", "state": "Wilayah Persekutuan",
        "pic_name": "Tan Sri Datuk Leong", "pic_email": "leong@mahsing.com.my", "pic_phone": "+60123456797",
        "contract_start": date(2024, 4, 1), "contract_end": date(2026, 3, 31),
        "sla_diversion_target": Decimal("60.00"), "billing_model": "tonnage",
    },
    {
        "company_name": "Sime Darby Plantation Sdn Bhd",
        "industry_vertical": "Agriculture / Palm Oil",
        "ssm_number": "199001101234",
        "address": "Menara Sime Darby, Ara Damansara",
        "city": "Petaling Jaya", "state": "Selangor",
        "pic_name": "Mohamad Helmy Othman", "pic_email": "helmy@simeply.com.my", "pic_phone": "+60123456798",
        "contract_start": date(2023, 6, 1), "contract_end": date(2025, 5, 31),
        "sla_diversion_target": Decimal("50.00"), "billing_model": "trip",
    },
]

VEHICLES = [
    {"registration": "WXY 1234", "vehicle_type": "compactor",   "make": "Hino",   "model": "500 Series", "year": 2021, "capacity_kg": Decimal("8000"), "gps_device_id": "GPS-001", "odometer_km": Decimal("45230")},
    {"registration": "WXY 5678", "vehicle_type": "compactor",   "make": "Hino",   "model": "500 Series", "year": 2020, "capacity_kg": Decimal("8000"), "gps_device_id": "GPS-002", "odometer_km": Decimal("67890")},
    {"registration": "WXY 9012", "vehicle_type": "hook_loader", "make": "Isuzu",  "model": "FVR",        "year": 2022, "capacity_kg": Decimal("12000"),"gps_device_id": "GPS-003", "odometer_km": Decimal("23450")},
    {"registration": "WXY 3456", "vehicle_type": "open_lorry",  "make": "Isuzu",  "model": "NMR",        "year": 2019, "capacity_kg": Decimal("5000"), "gps_device_id": "GPS-004", "odometer_km": Decimal("89120")},
    {"registration": "WXY 7890", "vehicle_type": "skip_truck",  "make": "Mitsubishi","model":"Fuso Canter","year": 2023,"capacity_kg": Decimal("6000"), "gps_device_id": "GPS-005", "odometer_km": Decimal("12340")},
    {"registration": "WXY 2345", "vehicle_type": "van",         "make": "Toyota", "model": "Hiace",      "year": 2022, "capacity_kg": Decimal("1500"), "gps_device_id": "GPS-006", "odometer_km": Decimal("34560")},
    {"registration": "WXY 6789", "vehicle_type": "compactor",   "make": "Fuso",   "model": "FM65F",      "year": 2021, "capacity_kg": Decimal("9000"), "gps_device_id": "GPS-007", "odometer_km": Decimal("56780")},
    {"registration": "WXY 9013", "vehicle_type": "skip_truck",  "make": "Isuzu",  "model": "FVR34L",     "year": 2022, "capacity_kg": Decimal("11000"),"gps_device_id": "GPS-008", "odometer_km": Decimal("28900")},
]

DOWNSTREAM_BUYERS = [
    {"company_name": "Papier Recycling Sdn Bhd",    "material_types": ["paper", "occ"],          "contact_name": "Tan Ah Kow",    "contact_phone": "+60123456800", "license_number": "DOE-REC-001"},
    {"company_name": "PET Recycle Malaysia Sdn Bhd","material_types": ["pet", "hdpe"],           "contact_name": "Ravi Kumar",    "contact_phone": "+60123456801", "license_number": "DOE-REC-002"},
    {"company_name": "Aluminium Recyclers Sdn Bhd", "material_types": ["aluminium", "ferrous"],  "contact_name": "Wong Chee Keong","contact_phone": "+60123456802","license_number": "DOE-REC-003"},
    {"company_name": "E-Waste Solutions Sdn Bhd",   "material_types": ["ewaste"],                "contact_name": "Siva Subramaniam","contact_phone": "+60123456803","license_number": "DOE-REC-004"},
]


async def seed():
    print("Starting database seed...")

    # Create all tables first (must happen before opening a session)
    print("Creating tables...")
    from database import create_all_tables
    await create_all_tables()
    print("Tables ready.")

    async with AsyncSessionLocal() as session:
        # ── Users ──────────────────────────────────────────────
        print("Seeding users...")
        user_ids = {}
        for u in USERS:
            uid = uuid.uuid4()
            user_ids[u["email"]] = uid
            await session.execute(text("""
                INSERT INTO users (id, email, hashed_password, full_name, role, is_active)
                VALUES (:id, :email, :pw, :name, :role, TRUE)
                ON CONFLICT (email) DO NOTHING
            """), {"id": uid, "email": u["email"], "pw": pwd_context.hash(u["password"]), "name": u["full_name"], "role": u["role"]})

        # ── Clients ────────────────────────────────────────────
        print("Seeding clients...")
        client_ids = {}
        for i, c in enumerate(CLIENTS):
            cid = uuid.uuid4()
            client_ids[c["company_name"]] = cid
            portal_uid = user_ids.get("portal@unilever.com.my") if i == 0 else None
            await session.execute(text("""
                INSERT INTO clients (id, company_name, industry_vertical, ssm_number, address, city, state,
                    pic_name, pic_email, pic_phone, portal_user_id, contract_start, contract_end,
                    sla_diversion_target, billing_model, is_active, created_at)
                VALUES (:id, :name, :ind, :ssm, :addr, :city, :state,
                    :pic_name, :pic_email, :pic_phone, :portal_uid, :cs, :ce, :sla, :bm, TRUE, NOW())
                ON CONFLICT DO NOTHING
            """), {
                "id": cid, "name": c["company_name"], "ind": c["industry_vertical"],
                "ssm": c["ssm_number"], "addr": c["address"], "city": c["city"], "state": c["state"],
                "pic_name": c["pic_name"], "pic_email": c["pic_email"], "pic_phone": c["pic_phone"],
                "portal_uid": portal_uid, "cs": c["contract_start"], "ce": c["contract_end"],
                "sla": c["sla_diversion_target"], "bm": c["billing_model"],
            })

        # ── Vehicles ───────────────────────────────────────────
        print("Seeding vehicles...")
        vehicle_ids = {}
        for i, v in enumerate(VEHICLES):
            vid = uuid.uuid4()
            vehicle_ids[v["registration"]] = vid
            svc_date = date.today() + timedelta(days=30 + i * 15)
            await session.execute(text("""
                INSERT INTO vehicles (id, registration, vehicle_type, make, model, year, capacity_kg,
                    gps_device_id, next_service_date, odometer_km, status, created_at)
                VALUES (:id, :reg, :vtype, :make, :model, :year, :cap,
                    :gps, :svc, :odo, 'available', NOW())
                ON CONFLICT (registration) DO NOTHING
            """), {
                "id": vid, "reg": v["registration"], "vtype": v["vehicle_type"],
                "make": v["make"], "model": v["model"], "year": v["year"],
                "cap": v["capacity_kg"], "gps": v["gps_device_id"],
                "svc": svc_date, "odo": v["odometer_km"],
            })

        # ── Downstream Buyers ──────────────────────────────────
        print("Seeding downstream buyers...")
        buyer_ids = {}
        for b in DOWNSTREAM_BUYERS:
            bid = uuid.uuid4()
            buyer_ids[b["company_name"]] = bid
            await session.execute(text("""
                INSERT INTO downstream_buyers (id, company_name, material_types, contact_name, contact_phone, license_number, is_active)
                VALUES (:id, :name, :mats, :contact, :phone, :lic, TRUE)
                ON CONFLICT DO NOTHING
            """), {"id": bid, "name": b["company_name"], "mats": b["material_types"],
                   "contact": b["contact_name"], "phone": b["contact_phone"], "lic": b["license_number"]})

        # ── Jobs ───────────────────────────────────────────────
        print("Seeding jobs...")
        job_ids = []
        client_list = list(client_ids.values())
        vehicle_list = list(vehicle_ids.values())
        job_types = ["general_collection", "scheduled_waste", "food_waste_bsf", "witnessed_destruction", "general_collection"]
        statuses = ["completed", "completed", "completed", "in_progress", "confirmed"]
        for i in range(20):
            jid = uuid.uuid4()
            job_ids.append(jid)
            jnum = f"JOB-2025-{i+1:04d}"
            sched = date.today() - timedelta(days=60 - i * 3)
            jtype = job_types[i % len(job_types)]
            jstatus = statuses[i % len(statuses)]
            completed_at = datetime(sched.year, sched.month, sched.day, 14, 0, tzinfo=timezone.utc) if jstatus == "completed" else None
            await session.execute(text("""
                INSERT INTO jobs (id, job_number, client_id, job_type, status, scheduled_date,
                    collection_address, assigned_vehicle_id, assigned_driver_id,
                    estimated_weight_kg, actual_weight_kg, disposal_route, completed_at, created_by,
                    created_at, updated_at)
                VALUES (:id, :jnum, :cid, :jtype, :status, :sched,
                    :addr, :vid, :did, :est, :act, :route, :comp, :creator, NOW(), NOW())
                ON CONFLICT (job_number) DO NOTHING
            """), {
                "id": jid, "jnum": jnum, "cid": client_list[i % len(client_list)],
                "jtype": jtype, "status": jstatus, "sched": sched,
                "addr": f"Lot {i+1}, Jalan Industri, Shah Alam, Selangor",
                "vid": vehicle_list[i % len(vehicle_list)],
                "did": user_ids["driver1@hitechwaste.com.my"],
                "est": Decimal(str(500 + i * 120)), "act": Decimal(str(480 + i * 115)) if jstatus == "completed" else None,
                "route": ["recycler", "cenviro", "bsf_farm", "landfill"][i % 4],
                "comp": completed_at, "creator": user_ids["ops@hitechwaste.com.my"],
            })

        # Commit jobs before inserting records that reference them
        await session.commit()

        # Read back actual job IDs from DB (handles ON CONFLICT DO NOTHING case
        # where jobs already existed with different UUIDs from a previous run)
        result = await session.execute(text(
            "SELECT id FROM jobs WHERE job_number LIKE 'JOB-2025-%' ORDER BY job_number"
        ))
        job_ids = [row[0] for row in result.fetchall()]

        # Also refresh client_list and vehicle_list from DB for downstream seeds
        result = await session.execute(text("SELECT id FROM clients ORDER BY created_at"))
        client_list = [row[0] for row in result.fetchall()]
        result = await session.execute(text("SELECT id FROM vehicles ORDER BY created_at"))
        vehicle_list = [row[0] for row in result.fetchall()]

        # Refresh user_ids from DB (ON CONFLICT DO NOTHING may have skipped inserts)
        result = await session.execute(text("SELECT email, id FROM users"))
        user_ids = {row[0]: row[1] for row in result.fetchall()}

        # Refresh buyer_ids from DB
        result = await session.execute(text("SELECT id FROM downstream_buyers ORDER BY company_name"))
        buyer_list = [row[0] for row in result.fetchall()]

        # ── Weighbridge Records ────────────────────────────────
        print("Seeding weighbridge records...")
        for i, jid in enumerate(job_ids[:15]):
            rec_time = datetime.now(timezone.utc) - timedelta(days=60 - i * 3, hours=2)
            gross = Decimal(str(5200 + i * 300))
            tare = Decimal("1800")
            await session.execute(text("""
                INSERT INTO weighbridge_records (id, job_id, client_id, recorded_at,
                    gross_weight_kg, tare_weight_kg, waste_type_breakdown, operator_id)
                VALUES (:id, :jid, :cid, :rat, :gross, :tare, cast(:breakdown as jsonb), :op)
                ON CONFLICT DO NOTHING
            """), {
                "id": uuid.uuid4(), "jid": jid, "cid": client_list[i % len(client_list)],
                "rat": rec_time, "gross": gross, "tare": tare,
                "breakdown": '{"recyclable_kg": ' + str(int((gross-tare)*Decimal("0.4"))) + ', "general_waste_kg": ' + str(int((gross-tare)*Decimal("0.5"))) + ', "food_waste_kg": ' + str(int((gross-tare)*Decimal("0.1"))) + '}',
                "op": user_ids["supervisor@hitechwaste.com.my"],
            })

        # ── Scheduled Waste Batches ────────────────────────────
        print("Seeding scheduled waste batches...")
        sw_data = [
            ("SW 305", "Used lubricating oil from machinery", Decimal("450"), "liquid", "200L drum", 3, 10),
            ("SW 410", "Lead-acid batteries from forklifts",  Decimal("280"), "solid",  "sealed bag", 8, 25),
            ("SW 420", "Electronic waste - circuit boards",   Decimal("120"), "solid",  "sealed bag", 5, 45),
            ("SW 305", "Hydraulic oil from press machines",   Decimal("380"), "liquid", "IBC",        2, 5),
            ("SW 410", "Lithium batteries from equipment",    Decimal("95"),  "solid",  "sealed bag", 12, 85),
        ]
        sw_job_ids = [job_ids[i] for i in range(min(5, len(job_ids)))]
        for i, (sw_code, desc, qty, state, container, count, days_ago) in enumerate(sw_data):
            storage_start = date.today() - timedelta(days=days_ago)
            status = "in_storage" if days_ago < 80 else "in_storage"
            await session.execute(text("""
                INSERT INTO scheduled_waste_batches (id, job_id, client_id, sw_code, waste_description,
                    quantity_kg, physical_state, container_type, container_count, storage_start_date, status)
                VALUES (:id, :jid, :cid, :sw, :desc, :qty, :state, :container, :count, :start, :status)
                ON CONFLICT DO NOTHING
            """), {
                "id": uuid.uuid4(), "jid": sw_job_ids[i], "cid": client_list[i % len(client_list)],
                "sw": sw_code, "desc": desc, "qty": qty, "state": state,
                "container": container, "count": count, "start": storage_start, "status": status,
            })

        # ── Recyclable Records ─────────────────────────────────
        print("Seeding recyclable records...")
        for i, jid in enumerate(job_ids[:10]):
            rec_time = datetime.now(timezone.utc) - timedelta(days=55 - i * 5)
            paper = 150 + i * 20; pet = 80 + i * 10; hdpe = 40 + i * 5
            aluminium = 25 + i * 3; ferrous = 60 + i * 8
            total = paper + pet + hdpe + aluminium + ferrous
            await session.execute(text("""
                INSERT INTO recyclable_records (id, job_id, client_id, recorded_at,
                    material_breakdown, total_recyclable_kg, buyer_id, sale_value_myr)
                VALUES (:id, :jid, :cid, :rat, cast(:breakdown as jsonb), :total, :buyer, :sale)
                ON CONFLICT DO NOTHING
            """), {
                "id": uuid.uuid4(), "jid": jid, "cid": client_list[i % len(client_list)],
                "rat": rec_time,
                "breakdown": '{"paper_kg":' + str(paper) + ',"pet_kg":' + str(pet) + ',"hdpe_kg":' + str(hdpe) + ',"aluminium_kg":' + str(aluminium) + ',"ferrous_kg":' + str(ferrous) + '}',
                "total": Decimal(str(total)),
                "buyer": buyer_list[i % len(buyer_list)],
                "sale": Decimal(str(round(total * 0.85, 2))),
            })

        # ── Carbon Records ─────────────────────────────────────
        print("Seeding carbon records...")
        for i, jid in enumerate(job_ids[:12]):
            transport = Decimal(str(round(15 + i * 2.5, 3)))
            landfill = Decimal(str(round(180 + i * 25, 3)))
            recycling = Decimal(str(round(95 + i * 15, 3)))
            wte = Decimal(str(round(20 + i * 5, 3)))
            net = transport - landfill - recycling - wte
            await session.execute(text("""
                INSERT INTO carbon_records (id, job_id, client_id, calculated_at,
                    transport_emissions_kgco2e, landfill_avoidance_kgco2e,
                    recycling_credit_kgco2e, wte_credit_kgco2e, net_carbon_impact_kgco2e,
                    methodology_notes)
                VALUES (:id, :jid, :cid, :cat, :trans, :landfill, :recycling, :wte, :net, :notes)
                ON CONFLICT DO NOTHING
            """), {
                "id": uuid.uuid4(), "jid": jid, "cid": client_list[i % len(client_list)],
                "cat": datetime.now(timezone.utc) - timedelta(days=50 - i * 4),
                "trans": transport, "landfill": landfill, "recycling": recycling,
                "wte": wte, "net": net,
                "notes": "Malaysia emission factors: diesel 2.68 kgCO2e/L, landfill 467 kgCO2e/t. WRAP recycling credits.",
            })

        # ── BSF Batches ────────────────────────────────────────
        print("Seeding BSF batches...")
        bsf_data = [
            (date.today() - timedelta(days=45), Decimal("850"), Decimal("127.5"), "clean", "completed"),
            (date.today() - timedelta(days=30), Decimal("620"), Decimal("93.0"),  "clean", "completed"),
            (date.today() - timedelta(days=15), Decimal("740"), None,             "minor", "active"),
            (date.today() - timedelta(days=5),  Decimal("510"), None,             "clean", "active"),
        ]
        for i, (intake, food_kg, larvae_kg, contam, bstatus) in enumerate(bsf_data):
            ratio = (larvae_kg / food_kg).quantize(Decimal("0.0001")) if larvae_kg else None
            await session.execute(text("""
                INSERT INTO bsf_batches (id, intake_date, source_job_ids, food_waste_kg,
                    client_sources, contamination_level, larvae_output_kg, conversion_ratio,
                    livestock_recipient, batch_start, status, created_at)
                VALUES (:id, :intake, :jobs, :food, cast(:sources as jsonb), :contam, :larvae, :ratio,
                    :recipient, :start, :status, NOW())
                ON CONFLICT DO NOTHING
            """), {
                "id": uuid.uuid4(), "intake": intake,
                "jobs": [str(job_ids[i % len(job_ids)])],
                "food": food_kg,
                "sources": '[{"client_id":"' + str(client_list[i % len(client_list)]) + '","client_name":"Client ' + str(i+1) + '","kg":' + str(food_kg) + '}]',
                "contam": contam, "larvae": larvae_kg, "ratio": ratio,
                "recipient": "Ayam Mas Poultry Farm, Sepang" if larvae_kg else None,
                "start": intake + timedelta(days=1), "status": bstatus,
            })

        # ── Agent Events ───────────────────────────────────────
        print("Seeding agent events...")
        agent_events = [
            ("compliance", "alert", "critical", "OVERDUE: SW 410 batch for Top Glove — 85 days stored", "SW 410 (Lead-acid batteries, 95 kg) for Top Glove Corporation has exceeded the 80-day warning threshold. Immediate disposal required.", "sw_batch"),
            ("compliance", "alert", "warning",  "Expiring Soon: SW 305 batch for Petronas — 5 days remaining", "SW 305 (Hydraulic oil, 380 kg) for Petronas Research will reach the 90-day storage limit in 5 days.", "sw_batch"),
            ("fleet",      "alert", "warning",  "Maintenance Due: WXY 5678 — 3 days", "Compactor WXY 5678 (Hino 500 Series) is due for scheduled service in 3 days. Current odometer: 67,890 km.", "vehicle"),
            ("esg",        "report","info",      "Weekly ESG Summary — w/e 13 Apr 2025", "Company-wide diversion rate this week: 68.4% (target: 70%). 3 clients below SLA target. Recommend reviewing waste segregation with KPJ Hospital.", "client"),
            ("operations", "alert", "warning",  "2 draft jobs not confirmed for today", "JOB-2025-0019 and JOB-2025-0020 remain in draft status. Resources must be assigned before dispatch.", "job"),
            ("billing",    "alert", "warning",  "Invoice INV-2025-0004 overdue by 15 days", "Client Nestle Malaysia has an outstanding invoice of RM 15,900.00 due since 30 Mar 2025. Consider follow-up call.", "invoice"),
            ("client",     "action","info",     "Client Intel Malaysia requires site visit", "New client Intel Malaysia (Kulim Hi-Tech Park) has requested an initial waste audit. Schedule assessment within 7 days.", "client"),
            ("compliance", "alert", "critical", "Compactor CM-004 overdue for maintenance", "Compaction machine CM-004 (Bramidan B5) is 5 days past scheduled maintenance. IMMEDIATE service required to maintain DOE compliance.", "compactor"),
            ("fleet",      "recommendation","info", "Route optimization available", "AI analysis shows 12% fuel savings possible on KLIA route by adjusting pickup sequence. Review recommended route: Sepang → KLIA → Cargo Village.", "route"),
            ("esg",        "alert", "info",     "Carbon credit opportunity", "Monthly recycling volume qualifies for additional carbon credits via Verra program. Estimated value: RM 4,200. Submit application by 20 Apr 2025.", "carbon"),
        ]
        for agent, etype, severity, title, body, ref_type in agent_events:
            await session.execute(text("""
                INSERT INTO agent_events (id, agent_name, event_type, severity, title, body, reference_type, is_read, created_at)
                VALUES (:id, :agent, :etype, :sev, :title, :body, :ref_type, FALSE, NOW())
                ON CONFLICT DO NOTHING
            """), {"id": uuid.uuid4(), "agent": agent, "etype": etype, "sev": severity,
                   "title": title, "body": body, "ref_type": ref_type})

        await session.commit()
        print("\nSeed complete!")
        print(f"  Users:              {len(USERS)}")
        print(f"  Clients:            {len(CLIENTS)}")
        print(f"  Vehicles:           {len(VEHICLES)}")
        print(f"  Downstream buyers:  {len(DOWNSTREAM_BUYERS)}")
        print(f"  Jobs:               20")
        print(f"  Weighbridge records: 15")
        print(f"  SW batches:         5")
        print(f"  Recyclable records: 10")
        print(f"  Carbon records:     12")
        print(f"  BSF batches:        4")
        print(f"  Agent events:       5")

        # ── Operational Field Management ───────────────────────
        print("\nSeeding operational field management data...")

        # Compaction machines
        compactor_ids = [uuid.uuid4() for _ in range(4)]
        compactors = [
            (compactor_ids[0], "CM-001", "Husmann HK-200", "HK200-2021-001", "deployed",
             date(2021, 3, 15), Decimal("200"), 90, date.today() - timedelta(days=5),
             date.today() + timedelta(days=85)),
            (compactor_ids[1], "CM-002", "Husmann HK-200", "HK200-2021-002", "available",
             date(2021, 6, 20), Decimal("200"), 90, date.today() - timedelta(days=30),
             date.today() + timedelta(days=60)),
            (compactor_ids[2], "CM-003", "Mil-tek 2000", "MT2000-2022-003", "deployed",
             date(2022, 1, 10), Decimal("180"), 90, date.today() - timedelta(days=10),
             date.today() + timedelta(days=10)),  # Due soon — will trigger alert
            (compactor_ids[3], "CM-004", "Bramidan B5", "B5-2023-004", "maintenance",
             date(2023, 5, 1), Decimal("150"), 90, date.today() - timedelta(days=95),
             date.today() - timedelta(days=5)),   # Overdue
        ]
        for cid, tag, model, serial, status, purchase, force, interval, last_svc, next_svc in compactors:
            await session.execute(text("""
                INSERT INTO compaction_machines (id, asset_tag, model_name, serial_number,
                    status, purchase_date, compaction_force_kn, maintenance_interval_days,
                    last_service_date, next_service_date, created_at, updated_at)
                VALUES (:id, :tag, :model, :serial, :status, :purchase, :force, :interval,
                    :last_svc, :next_svc, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """), {
                "id": cid, "tag": tag, "model": model, "serial": serial,
                "status": status, "purchase": purchase, "force": force,
                "interval": interval, "last_svc": last_svc, "next_svc": next_svc,
            })

        # Containers (simplified - no compactor links)
        container_ids = [uuid.uuid4() for _ in range(6)]
        containers = [
            (container_ids[0], "CNT-001", "roll_on_roll_off", Decimal("20"), "at_site",
             client_list[0], "Lot 5, Jalan Tandang, PJ", "cardboard", 72, 85),
            (container_ids[1], "CNT-002", "roll_on_roll_off", Decimal("20"), "at_site",
             client_list[0], "Lot 5, Jalan Tandang, PJ", "plastics", 45, 85),
            (container_ids[2], "CNT-003", "skip_bin", Decimal("10"), "at_site",
             client_list[1], "Nestle Malaysia, Jalan Damansara", "metals", 88, 85),
            (container_ids[3], "CNT-004", "compaction_chamber", Decimal("30"), "available",
             None, None, None, 0, 85),
            (container_ids[4], "CNT-005", "skip_bin", Decimal("10"), "in_transit",
             None, "In transit to Petronas", None, 0, 85),
            (container_ids[5], "CNT-006", "roll_on_roll_off", Decimal("20"), "at_depot",
             None, "Hi-Tech Depot, Shah Alam", None, 0, 85),
        ]
        for cid, code, ctype, cap, loc, clid, addr, waste, fill, threshold in containers:
            await session.execute(text("""
                INSERT INTO containers (id, container_code, container_type, capacity_m3, status,
                    current_client_id, current_site_address, target_material_type, fill_level,
                    pickup_threshold, created_at, updated_at)
                VALUES (:id, :code, :ctype, :cap, :loc, :clid, :addr, :waste, :fill, :threshold, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """), {
                "id": cid, "code": code, "ctype": ctype, "cap": cap, "loc": loc,
                "clid": clid, "addr": addr, "waste": waste,
                "fill": fill, "threshold": threshold,
            })

        # Staff profiles (link to existing users)
        supervisor_id = user_ids.get("supervisor@hitechwaste.com.my")
        driver1_id = user_ids.get("driver1@hitechwaste.com.my")
        driver2_id = user_ids.get("driver2@hitechwaste.com.my")

        staff_profile_ids = {}
        staff_data = [
            (supervisor_id, "permanent", None, "on_site", None),
            (driver1_id, "permanent", None, "on_site", None),
            (driver2_id, "contract", "Manpower Malaysia Sdn Bhd", "available", None),
        ]
        for user_id, emp_type, agent, status, permit_expiry in staff_data:
            if user_id:
                pid = uuid.uuid4()
                staff_profile_ids[str(user_id)] = pid
                await session.execute(text("""
                    INSERT INTO staff_profiles (id, user_id, employment_type,
                        labour_agent_name, assignment_status, work_permit_expiry,
                        created_at, updated_at)
                    VALUES (:id, :uid, :emp_type, :agent, :status, :permit, NOW(), NOW())
                    ON CONFLICT (user_id) DO NOTHING
                """), {
                    "id": pid, "uid": user_id, "emp_type": emp_type,
                    "agent": agent, "status": status, "permit": permit_expiry,
                })

        # Site assignment
        site_assignment_id = uuid.uuid4()
        await session.execute(text("""
            INSERT INTO site_assignments (id, client_id, site_address, supervisor_id,
                start_date, is_active, created_by, created_at, updated_at)
            VALUES (:id, :cid, :addr, :sup, :start, TRUE, :created_by, NOW(), NOW())
            ON CONFLICT DO NOTHING
        """), {
            "id": site_assignment_id,
            "cid": client_list[0],
            "addr": "Lot 5, Jalan Tandang, Petaling Jaya Industrial Area",
            "sup": supervisor_id,
            "start": date.today() - timedelta(days=14),
            "created_by": user_ids.get("ops@hitechwaste.com.my"),
        })

        # Disruption logs
        disruption_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        disruptions = [
            (disruption_ids[0], "landfill_delay", "open", "warning",
             datetime.now(timezone.utc) - timedelta(hours=2),
             "Bukit Tagar Sanitary Landfill is experiencing 3-hour queues due to heavy rain. "
             "All vehicles heading to landfill are delayed.",
             None, None, None, None),
            (disruption_ids[1], "vehicle_breakdown", "open", "critical",
             datetime.now(timezone.utc) - timedelta(hours=5),
             "WXY 1234 (16-ton lorry) has broken down on the Federal Highway near Subang. "
             "Engine failure. Tow truck dispatched.",
             vehicle_list[0] if vehicle_list else None, None, None, None),
            (disruption_ids[2], "highway_restriction", "resolved", "info",
             datetime.now(timezone.utc) - timedelta(days=1),
             "PLUS Highway restricts heavy vehicles between 7am-9am and 5pm-8pm on weekdays.",
             None, "PLUS Highway (E1)", time(7, 0), time(9, 0)),
        ]
        for (did, dtype, status, severity, occurred, desc,
             vehicle_id, highway, rest_start, rest_end) in disruptions:
            # Build affected_job_ids as a Python list for the ARRAY param
            affected = [str(job_ids[0])] if job_ids else []
            if len(job_ids) > 1:
                affected.append(str(job_ids[1]))

            await session.execute(text("""
                INSERT INTO disruption_logs (id, disruption_type, status, severity,
                    occurred_at, reported_by, description, affected_job_ids,
                    vehicle_id, highway_name, restriction_start_time, restriction_end_time,
                    resolution_history, created_at, updated_at)
                VALUES (:id, :dtype, :status, :severity, :occurred, :reported_by,
                    :desc, :affected_jobs, :vehicle_id, :highway,
                    CAST(:rest_start AS time), CAST(:rest_end AS time),
                    '[]'::jsonb, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """), {
                "id": did, "dtype": dtype, "status": status, "severity": severity,
                "occurred": occurred,
                "reported_by": user_ids.get("driver1@hitechwaste.com.my"),
                "desc": desc,
                "affected_jobs": affected,
                "vehicle_id": vehicle_id,
                "highway": highway,
                "rest_start": rest_start,
                "rest_end": rest_end,
            })

        # Invoices for finance module demo
        print("Seeding invoices...")
        invoice_statuses = ["unpaid", "partial", "paid", "overdue"]
        for i in range(15):
            inv_num = f"INV-2025-{i+1:04d}"
            client = client_list[i % len(client_list)]
            subtotal = Decimal(str(2500 + i * 500))
            tax = subtotal * Decimal("0.06")
            total = subtotal + tax
            status = invoice_statuses[i % len(invoice_statuses)]
            paid = Decimal("0")
            if status == "paid":
                paid = total
            elif status == "partial":
                paid = total * Decimal("0.5")
            
            issue = date.today() - timedelta(days=30 - i * 2)
            due = issue + timedelta(days=30)
            
            await session.execute(text("""
                INSERT INTO invoices (id, invoice_number, client_id, issue_date, due_date,
                    line_items, subtotal_myr, tax_myr, total_myr, status, paid_amount_myr,
                    notes, created_at, updated_at)
                VALUES (:id, :num, :cid, :issue, :due,
                    cast(:lines as jsonb), :subtotal, :tax, :total, :status, :paid,
                    :notes, NOW(), NOW())
                ON CONFLICT (invoice_number) DO NOTHING
            """), {
                "id": uuid.uuid4(), "num": inv_num, "cid": client,
                "issue": issue, "due": due,
                "lines": '[{"description":"Waste collection services","quantity":' + str(10+i) + ',"unit":"trip","unit_price":250.00,"amount":' + str(float(subtotal)) + '}]',
                "subtotal": subtotal, "tax": tax, "total": total,
                "status": status, "paid": paid,
                "notes": "Payment terms: Net 30 days" if status in ["unpaid", "overdue"] else "Payment received - thank you!",
            })

        await session.commit()
        print("\nSeed complete!")
        print(f"  Users:              {len(USERS)}")
        print(f"  Clients:            {len(CLIENTS)}")
        print(f"  Vehicles:           {len(VEHICLES)}")
        print(f"  Downstream buyers:  {len(DOWNSTREAM_BUYERS)}")
        print(f"  Jobs:               20")
        print(f"  Weighbridge records: 15")
        print(f"  SW batches:         5")
        print(f"  Recyclable records: 10")
        print(f"  Carbon records:     12")
        print(f"  BSF batches:        4")
        print(f"  Agent events:       10")
        print(f"  Compaction machines: 4")
        print(f"  Containers:         6")
        print(f"  Staff profiles:     3")
        print(f"  Site assignments:   1")
        print(f"  Disruption logs:    3")
        print(f"  Invoices:           15")


if __name__ == "__main__":
    asyncio.run(seed())
