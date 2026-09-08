import pytest
from app import app, znamka_from_percentage, build_home_stats, get_student_name

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


def test_best_subject_ranks_by_percentage_not_grade():
    # Matematika and Fyzika both round to grade "1", but Fyzika has the
    # higher percentage - best subject should follow percentage, not grade.
    subjects_display = [
        ["1", "Matematika", "1", "1", "91,00%", "45 / 50"],
        ["2", "Fyzika", "1", "1", "98,50%", "49 / 50"],
        ["3", "Dějepis", "3", "3", "65,00%", "33 / 50"],
    ]
    stats = build_home_stats(subjects_display, [])
    assert stats["best_subject"] == "Fyzika"


def test_best_subject_falls_back_to_grade_without_percentages():
    subjects_display = [
        ["1", "Matematika", "2", "2", "-", "-"],
        ["2", "Fyzika", "1", "1", "N", "-"],
    ]
    stats = build_home_stats(subjects_display, [])
    assert stats["best_subject"] == "Fyzika"


def test_get_student_name_from_navbar():
    # Real markup confirmed by live inspection - see docs/investigate-is-psjg.md
    html = """
    <html><head><title>Kunc Maxmilian | PSJG</title></head>
    <body>
      <nav id="mainNav" class="navbar navbar-expand-lg navbar-dark bg-white absolute-top">
        <div id="navbarResponsive" class="collapse navbar-collapse">
          <ul class="navbar-nav ml-auto">
            <li class="nav-item nav-username">Kunc Maxmilian</li>
          </ul>
        </div>
      </nav>
    </body></html>
    """
    assert get_student_name(html) == "Kunc Maxmilian"


def test_get_student_name_falls_back_to_title():
    html = '<html><head><title>Kunc Maxmilian | PSJG</title></head><body></body></html>'
    assert get_student_name(html) == "Kunc Maxmilian"


def test_get_student_name_none_when_neither_present():
    html = "<html><head></head><body><p>no name here</p></body></html>"
    assert get_student_name(html) is None