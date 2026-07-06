import pytest
from app import create_app, db
from models import User, Song, Notification
from services.notification_service import rate_song

@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

def test_rate_song_creates_notification(app):
    """Rating a friend's song should generate a notification for the sharer."""
    with app.app_context():
        # Setup: Create a sharer, a rater, and a song
        sharer = User(username="sharer", email="sharer@test.com")
        rater = User(username="rater", email="rater@test.com")
        db.session.add_all([sharer, rater])
        db.session.commit()

        song = Song(title="Test Song", artist="Test Artist", genre="pop", shared_by=sharer.id)
        db.session.add(song)
        db.session.commit()

        # Action: The rater rates the song
        rate_song(user_id=rater.id, song_id=song.id, score=5)

        # Assert: The sharer should have received exactly 1 notification
        notifications = db.session.query(Notification).filter_by(user_id=sharer.id).all()
        assert len(notifications) == 1
        assert notifications[0].notification_type == "song_rated"