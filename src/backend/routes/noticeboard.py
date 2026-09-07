from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.database.models import Holiday
print("NOTICEBOARD ROUTE LOADED")
router = APIRouter(
    prefix="/noticeboard",
    tags=["Notice Board"]
)

@router.get("/holidays")
def get_notice_board(db: Session = Depends(get_db)):

    holidays = (
        db.query(Holiday)
        .order_by(Holiday.date.desc())
        .all()
    )

    return [
        {
            "id": h.id,
            "name": h.name,
            "date": str(h.date),
            "description": h.description
        }
        for h in holidays
    ]