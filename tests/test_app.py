import pytest
from app import app, znamka_from_percentage

@pytest.fixture()
def client():
    app.config['TESTING'] = True
    # Pokud používáš Flask-Session (filesystem), 
    # v testech to obvykle chceme vypnout nebo použít paměť
    with app.test_client() as client:
        yield client


def test_serve_frontend_root(client):
    # No frontend_dist/ in the test environment (it's only built inside the
    # Docker image) - the catch-all should still respond 200, not crash.
    response = client.get("/")
    assert response.status_code == 200


def test_api_session_unauthenticated(client):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.get_json() == {"authenticated": False}

def test_grade_calculation():
    assert znamka_from_percentage("100%") == 1
    assert znamka_from_percentage("91%") == 1
    assert znamka_from_percentage("90%") == 2
    assert znamka_from_percentage("80%") == 2
    assert znamka_from_percentage("79%") == 3
    assert znamka_from_percentage("60%") == 3
    assert znamka_from_percentage("59%") == 4
    assert znamka_from_percentage("45%") == 4
    assert znamka_from_percentage("44%") == 5
    assert znamka_from_percentage("0%") == 5
    assert znamka_from_percentage("-") == -1
    assert znamka_from_percentage("N") == "N"