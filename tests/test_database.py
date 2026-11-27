from app.models.user import User


def test_database_session_can_insert_and_read_user(db_session):
    user = User(
        username="alice",
        email="alice@example.com",
        password_hash="hashed-password",
        display_name="Alice",
    )

    db_session.add(user)
    db_session.commit()

    stored_user = db_session.query(User).filter_by(email="alice@example.com").one()

    assert stored_user.username == "alice"
    assert stored_user.display_name == "Alice"
    assert stored_user.is_active is True
