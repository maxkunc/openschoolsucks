import pytest
from app import app, znamka_from_percentage

@pytest.fixture()
def client():
    app.config['TESTING'] = True
    # Pokud používáš Flask-Session (filesystem), 
    # v testech to obvykle chceme vypnout nebo použít paměť
    with app.test_client() as client:
        yield client


def test_request_login(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b'<input type="submit" value="P\xc5\x99ihl\xc3\xa1sit se">' in response.data

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