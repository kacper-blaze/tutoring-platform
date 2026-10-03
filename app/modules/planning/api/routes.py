"""
Router modułu Planowanie i Dostępność (sekcja 5.10).

Wszystkie endpointy zarządzania grafikiem wymagają JWT korepetytora
(rola TUTOR). Endpoint odczytu wolnych terminów jest publiczny.
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.planning.api.schemas import (
    PublicSlotItem,
    PublicSlotsResponse,
    SetAvailabilityRequest,
    SetAvailabilityResponse,
    SlotResponse,
)
from app.modules.planning.application.planning_service import PlanningService
from app.modules.users.api.dependencies import require_role
from app.modules.users.domain.models import UserAccount

router = APIRouter(tags=["Planowanie i Dostępność"])


@router.put("/schedules/me/availability", response_model=SetAvailabilityResponse)
def set_availability(
    payload: SetAvailabilityRequest,
    db: Session = Depends(get_db),
    tutor: UserAccount = Depends(require_role("TUTOR")),
):
    """UC-P01/UC-P02 - zdefiniowanie lub modyfikacja reguł dostępności i materializacja slotów."""
    service = PlanningService(db)
    rules = [
        {
            "day_of_week": r.dayOfWeek,
            "start_time": r.startTime,
            "end_time": r.endTime,
            "valid_from": r.validFrom,
            "valid_until": r.validUntil,
        }
        for r in payload.rules
    ]
    result = service.set_availability(tutor.id, rules)
    return SetAvailabilityResponse(**result)


@router.post("/slots/{slot_id}/block", response_model=SlotResponse)
def block_slot(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    tutor: UserAccount = Depends(require_role("TUTOR")),
):
    """UC-P03 - ręczne zablokowanie wolnego terminu przez korepetytora."""
    slot = PlanningService(db).block_slot(tutor.id, slot_id)
    return SlotResponse(slotId=slot.id, status=slot.status)


@router.post("/slots/{slot_id}/unblock", response_model=SlotResponse)
def unblock_slot(
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
    tutor: UserAccount = Depends(require_role("TUTOR")),
):
    """Zwolnienie ręcznie zablokowanego terminu (odwrotność UC-P03)."""
    slot = PlanningService(db).unblock_slot(tutor.id, slot_id)
    return SlotResponse(slotId=slot.id, status=slot.status)


@router.get("/tutors/{tutor_id}/slots", response_model=PublicSlotsResponse)
def get_public_slots(
    tutor_id: uuid.UUID,
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    db: Session = Depends(get_db),
):
    """Endpoint publiczny - wolne terminy korepetytora w zadanym zakresie dat (sekcja 5.10)."""
    slots = PlanningService(db).get_public_slots(tutor_id, date_from, date_to)
    return PublicSlotsResponse(
        tutorId=tutor_id,
        slots=[
            PublicSlotItem(slotId=s.id, startTime=s.start_time, durationMinutes=s.duration_minutes) for s in slots
        ],
    )
