from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.dependencies import get_db
from apps.api.schemas import FAQSearchResponse
from db.models import FAQDocument

router = APIRouter(
    prefix="/faq",
    tags=["faq"],
)


@router.get(
    "/search",
    response_model=list[FAQSearchResponse],
)
def search_faq(
    q: str,
    db: Session = Depends(get_db),
) -> list[FAQSearchResponse]:
    stmt = (
        select(FAQDocument)
        .where(
            FAQDocument.question.ilike(
                f"%{q}%"
            )
        )
        .limit(5)
    )

    results = db.scalars(stmt).all()

    return [
        FAQSearchResponse(
            id=item.id,
            category=item.category,
            question=item.question,
            approved_answer=item.approved_answer,
        )
        for item in results
    ]
