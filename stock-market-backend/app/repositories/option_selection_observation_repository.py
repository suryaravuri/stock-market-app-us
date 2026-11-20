from sqlalchemy.orm import Session

from app.models.option_selection_observation import (
    OptionSelectionObservation,
)


class OptionSelectionObservationRepository:

    @staticmethod
    def save(
        db: Session,
        observation: OptionSelectionObservation,
    ) -> OptionSelectionObservation:

        db.add(observation)
        db.commit()
        db.refresh(observation)

        return observation