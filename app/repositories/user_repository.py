from sqlalchemy.orm import Session

from app.models.user import User


def get_or_create_user(db: Session, line_user_id: str, display_name: str | None = None) -> User:
    user = db.query(User).filter(User.line_user_id == line_user_id).one_or_none()
    if user is not None:
        if display_name and user.display_name != display_name:
            user.display_name = display_name
            db.commit()
            db.refresh(user)
        return user

    user = User(line_user_id=line_user_id, display_name=display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
