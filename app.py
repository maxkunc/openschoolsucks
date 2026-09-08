###############################
# Made by Krupicova12Kase AKA Máťa
# Licensed under MIT license
# Report any bugs at https://github.com/Krupicova12Kase/OpenSchoolSucks/issues
###############################

# Imports
import concurrent.futures
import traceback
from flask import Flask, request, jsonify, abort, send_from_directory, session as flask_session_custom
from flask_session import Session
import os
import tempfile
import requests
from ssl import get_server_certificate
from urllib.parse import urlparse, parse_qs
import urllib3
from bs4 import BeautifulSoup, diagnose
from io import StringIO
import re
import pandas as pd
from dotenv import load_dotenv
from colorama import init, Fore
from cachelib import FileSystemCache
from cert_chain_resolver.api import resolve

# Load environment variables
load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# Server side session: the real is.psjg.cz auth cookies are too large to fit in a
# single signed client-side cookie, so this has to be a server-side store.
# NOTE: this means the app needs a persistent/writable filesystem and does NOT work
# on stateless serverless hosts (e.g. Vercel) - see README for that tradeoff.
#
# cache_dir must be a writable absolute path, not a plain relative one: a
# relative path resolves inside the app's own deployment directory, which is
# read-only on hosts like Vercel (same reason CERTIFICATE_DIR below uses a
# tmp dir instead of a repo-relative path). Using the same pattern here means
# the very first session write - right after a successful is.psjg.cz login -
# doesn't throw and get swallowed into a generic 500.
SESSION_DIR = os.environ.get("SESSION_DIR") or os.path.join(tempfile.gettempdir(), "openschoolsucks-flask-session")
os.makedirs(SESSION_DIR, exist_ok=True)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "cachelib"
app.config["SESSION_CACHELIB"] = FileSystemCache(cache_dir=SESSION_DIR)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# The React app is built into FRONTEND_DIST and served by this same Flask
# process (see serve_frontend() at the bottom), so API calls from it are
# same-origin - no CORS, no separate FRONTEND_ORIGIN, no VITE_API_URL needed.
# SESSION_COOKIE_SECURE still matters even same-origin: turn it on whenever
# this is served over HTTPS (the norm in production).
app.config['SESSION_COOKIE_SAMESITE'] = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'False') == 'True'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'cs-CZ,cs;q=0.9,en;q=0.8',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
}

# (connect timeout, read timeout) in seconds, applied to every request to
# is.psjg.cz. requests has no timeout by default, so a slow/hung upstream
# connection used to be able to block a request indefinitely instead of
# failing fast with a clear error the frontend can show.
REQUEST_TIMEOUT = (5, 20)

Session(app)


# CERTIFICATES

# Use a writable temp dir rather than a path inside the repo, since the app's own
# directory is read-only on serverless hosts (e.g. Vercel only allows writes to /tmp).
CERTIFICATE_DIR = os.environ.get("CERTIFICATE_DIR") or os.path.join(tempfile.gettempdir(), "openschoolsucks-certificates")
os.makedirs(CERTIFICATE_DIR, exist_ok=True)
certificate_chain_path = os.path.join(CERTIFICATE_DIR, "psjg_chain.crt")
certificate_file = "custom"


def certificates() -> None:
    """Generate full certificate chain using cert_chain_resolver because is.psjg.cz sends incomplete
    """
    half_chain_path = os.path.join(CERTIFICATE_DIR, "psjg_half_chain.crt")
    psjg_certificate = str(get_server_certificate(("is.psjg.cz", 443)))

    with open(half_chain_path, "w") as f:
        f.write(psjg_certificate)

    with open(half_chain_path, 'rb') as f1:
        fb = f1.read()
        chain = resolve(fb)

        with open(certificate_chain_path, "w", encoding="utf-8") as f2:
            for cert in chain:
                f2.write(str(cert.export()))
    print("Obtained certificates successfully!")


def _resolve_certificate_chain(timeout_seconds: int = 15) -> None:
    """Run certificates() under a hard timeout.

    Neither get_server_certificate() nor cert_chain_resolver's own network
    calls take a timeout, so without this a slow/hanging is.psjg.cz can
    block app boot indefinitely instead of just failing this one step.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(certificates).result(timeout=timeout_seconds)


if os.environ.get('VERIFY', 'True') == 'True':
    try:
        _resolve_certificate_chain()
        certificate = certificate_chain_path
    except Exception:
        # Cold start on a host with restricted/no outbound network access, is.psjg.cz
        # unreachable, or the chain fetch just took too long - reuse a chain fetched
        # by an earlier warm invocation if there is one. This must never crash app
        # boot: CERTIFICATE_DIR lives on an ephemeral tmp dir on hosts like Render,
        # so every cold start (including every restart after a crash) starts with no
        # cache and has to refetch the chain from scratch - a single transient
        # failure here used to crash-loop the whole process forever.
        print(traceback.format_exc())
        if os.path.exists(certificate_chain_path):
            print(f"{Fore.YELLOW}Failed to refresh certificate chain, reusing the cached one{Fore.RESET}")
            certificate = certificate_chain_path
        else:
            print(f"{Fore.RED}Failed to obtain a certificate chain and no cached one exists - "
                  f"booting with SSL verification disabled instead of crash-looping{Fore.RESET}")
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            certificate = False
else:
    print(f"{Fore.RED}!! SSL Verification disabled !!{Fore.RESET}")
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    certificate = False


def delete_spaces(text: str) -> str:
    """ Deletes unnecessary spaces, tabs and newlines from text

    Args:
        text (str): Text to change

    Returns:
        str: Chnaged text
    """
    return re.sub(r'\s+', ' ', text.strip())


def csv_to_dataframe(text: str) -> pd.DataFrame:
    """Convert provided text to dataframe. Text needs to be in CSV format

    Args:
        text (str): Text to convert

    Returns:
        pd.DataFrame: pandas DataFrame
    """
    df = pd.read_csv(StringIO(text), sep=';')
    return df


def get_info(text: str) -> int:
    """Get info about student from text from is.psjg.cz. Currently returns only student id

    Args:
        text (str): raw HTML

    Returns:
        int: The student id
    """
    # Get full HTML webpage
    soup = BeautifulSoup(text, "html.parser")
    search = soup.find_all(title="Téma studentského portfolia")
    if len(search) > 1 or len(search) < 1:
        abort(500, f"Found {len(search)} student ids")

    href = search[0].a["href"]
    id_part = href[href.rfind("/") + 1:href.find("?") if "?" in href else None]
    try:
        student_id = int(id_part)
    except ValueError:
        abort(500, f"Failed to convert to integer {id_part}")

    return student_id


def get_student_name(text: str) -> str | None:
    """Extract the student's real name from is.psjg.cz page HTML.

    Confirmed by live inspection (see docs/investigate-is-psjg.md): every
    page's navbar server-renders it as
    <li class="nav-item nav-username">Name</li> - not JS-injected, so a
    plain requests.get() sees it. Falls back to the <title> tag
    ("Name | PSJG"), also confirmed present, if the navbar element is
    ever missing.

    Args:
        text (str): raw HTML from is.psjg.cz

    Returns:
        str | None: the student's name, or None if neither source had it
    """
    soup = BeautifulSoup(text, "html.parser")

    nav_username = soup.find("li", class_="nav-username")
    if nav_username:
        name = delete_spaces(nav_username.get_text())
        if name:
            return name

    if soup.title and soup.title.string:
        name = delete_spaces(soup.title.string.split("|")[0])
        if name:
            return name

    return None


def get_csv_subjects(text: str, fieldnames: list) -> pd.DataFrame:
    """Get subjects from HTML of mainpage

    Args:
        text (str): raw HTML from is.psjg.cz
        fieldnames (list): List of filednames for DataFrame

    Returns:
        pd.DataFrame: Dataframe with subjects
    """
    df = pd.DataFrame(columns=fieldnames)
    soup = BeautifulSoup(text, "html.parser")
    try:
        # Find all tables in the HTML file
        for table in soup.find_all('table'):
            if table.tr.th.text == "Předmět":  # Search only for table with list of subjects
                for tr in table.find_all('tr'):  # Iterate through rows
                    sezam = []
                    # Iterate through columns
                    for i, td in enumerate(tr.find_all('td')):
                        if not td.a is None:
                            url = td.a.get("href")  # Get URL from link
                            query = urlparse(url).query
                            params = parse_qs(query)
                            subject_id = params.get('subjectId')[0]
                            sezam.append(subject_id)
                        sezam.append(delete_spaces(td.text))

                        if i == 3:
                            df.loc[len(df)] = sezam

        return df
    except Exception as e:
        print(traceback.format_exc())
        print(diagnose(soup))
        abort(500)


def get_portfolio(text: str) -> dict:
    """Gets portfolio info from HTML. for example return, see example.jsonc

    Args:
        text (str): raw HTML from is.psjg.cz/achievement

    Raises:
        Exception: _description_
        Exception: _description_
        Exception: _description_

    Returns:
        dict: Dictionary with total points, place and info about each entry
    """
    soup = BeautifulSoup(text, "html.parser")
    portfoliodict = {}
    data = []
    try:
        # dict
        for div in soup.find_all("div", class_="row_achievement"):
            subdict = {}
            total_points = 0
            tableVar = div.find_all("table")

            # Checks
            if not tableVar:
                raise Exception("Failed to find table in div")
            tbodyList = div.table.find_all("tbody")
            if len(tbodyList) >= 2 or not div.table.tbody:
                abort(500)
                raise Exception(
                    f"Failed to get tbodies. found {tbodyList.len()} total.")

            tBodyVar = tbodyList[0]

            items = []
            for tr in tBodyVar.find_all("tr"):
                tdVar = tr.find_all("td")

                # subsubdict
                subsubdict = {}
                subsubdict["name"] = delete_spaces(tdVar[0].get_text())
                subsubdict["points"] = delete_spaces(tdVar[1].get_text())
                total_points += int(delete_spaces(tdVar[1].get_text()))
                subsubdict["description"] = delete_spaces(tdVar[2].get_text())
                items.append(subsubdict)

            # Heading
            h2 = div.find("h2")
            if not h2:
                abort(500)
                raise Exception("Failed to find h2")
            name = delete_spaces(h2.get_text())

            # subdict
            if not len(items) == 0:
                subdict["name"] = name
                subdict["items"] = items
                subdict["points"] = total_points
                data.append(subdict)

        # Total points and place
        total = soup.find("div", class_="col-md-6 offset-md-3").find("div").find("h2").get_text()
        points = delete_spaces(total[total.find(": ") + 2:total.find(" b")])  # Extract points
        place = delete_spaces(total[total.find("(") + 1:total.find(". v")])  # Extract place

        try:
            points = int(points)
            place = int(place)
        except ValueError as e:
            print(f"Error converting to integer: {e}")
            abort(500)

        portfoliodict["data"] = data
        portfoliodict["points"] = points
        portfoliodict["place"] = place

    except Exception as e:
        print(traceback.format_exc())
        abort(500)
    return portfoliodict


def get_exams(text: str) -> list[dict]:
    """Parses the Zkoušení (oral exam schedule) table from
    is.psjg.cz/exam/student-view.

    Confirmed by live inspection (see docs/investigate-is-psjg.md): unlike
    grades/portfolio, this page has no CSV export component at all, so this
    parses the rendered HTML table directly. Columns: Název, Datum,
    Třída/Skupina, Předmět, Čtvrtletní zkoušení.

    Args:
        text (str): raw HTML from is.psjg.cz/exam/student-view

    Returns:
        list[dict]: exam rows (possibly empty - schools that don't use this
        feature genuinely have zero rows, confirmed live, not a parsing bug)
    """
    soup = BeautifulSoup(text, "html.parser")
    table = soup.select_one("div.table-responsive div.tf-wrapper table.table") or soup.find("table", class_="table")
    if not table:
        return []

    body = table.find("tbody") or table
    exams = []
    for row in body.find_all("tr"):
        cells = [delete_spaces(cell.get_text()) for cell in row.find_all(["td", "th"])]
        if len(cells) < 5 or not any(cells):
            continue
        exams.append({
            "name": cells[0],
            "date": cells[1],
            "group": cells[2],
            "subject": cells[3],
            "quarterly": cells[4],
        })
    return exams


def get_semesters(text: str) -> tuple[list[str], int | None]:
    """Get list of semesters and which one is.psjg.cz currently has active.

    Example return: (["2026/27 - První pololetí", "2026/27 - Druhé pololetí"], 0)

    Args:
        text (str): HTML from homepage of is.psjg.cz

    Returns:
        tuple[list[str], int | None]: (semester labels, 0-based index of the
        <option> is.psjg.cz marked selected - i.e. its own default when no
        semesterId was requested - or None if that couldn't be determined)
    """

    soup = BeautifulSoup(text, "html.parser")
    select = soup.find_all("select", id="frm-switchSemester-semester")
    options = select[0].find_all("option") if select else []

    labels = [option.text for option in options]
    selected_index = next((i for i, o in enumerate(options) if o.has_attr("selected")), None)

    return labels, selected_index


def get_semester_number(semester: str) -> int:
    # 2021/22 - První pololetí
    semester = semester.strip()
    try:
        number = int(semester[2:semester.find("/")]) - 18
        return number * 2 + 1 if not "D" in semester else number * 2 + 2
    except ValueError:
        return -1


def znamka_from_percentage(percentage) -> int | str:
    """Gets number grade from percentage. Returns 0 if percentrage is too low / too high

    Args:
        percentage (_type_): _description_

    Returns:
        int | str: Grade (-1 - 5) or "N"
    """
    if str(percentage) == "-":
        return -1
    if str(percentage) == "N":
        return "N"
    if str(percentage)[len(percentage) - 1] == "%":
        percentage = percentage[:len(percentage) - 1]
        percentage = percentage.replace(",", ".")
        percentage = float(percentage)
    if percentage >= 91:
        return 1
    elif percentage >= 80:
        return 2
    elif percentage >= 60:
        return 3
    elif percentage >= 45:
        return 4
    elif percentage >= 0:
        return 5
    else:
        return 0


def parse_grade(value) -> float | None:
    """Parse a Czech grade value (e.g. "1", "1,5", "N", "-") into a float, if possible

    Args:
        value: Raw grade value

    Returns:
        float | None: Parsed grade or None if it isn't a plain numeric grade
    """
    try:
        return float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        return None


def parse_percent_value(value) -> float | None:
    """Parse a percentage value like "91,75%" into a float, if possible.

    Args:
        value: Raw percentage value

    Returns:
        float | None: Parsed percentage or None if it isn't a plain numeric one
    """
    try:
        return float(str(value).strip().replace("%", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def build_home_stats(subjects_display: list, znamky: list) -> dict:
    """Build small dashboard stats (average grade, best subject, counts) from home page data

    Args:
        subjects_display (list): Rows of [id, name, known_grade, final_grade, percentage, points]
        znamky (list): Rows of individual grades

    Returns:
        dict: Stats for the dashboard cards
    """
    graded_subjects = [row for row in subjects_display if parse_grade(row[2]) is not None]

    if graded_subjects:
        average = sum(parse_grade(row[2]) for row in graded_subjects) / len(graded_subjects)
        avg_grade = f"{average:.2f}".rstrip("0").rstrip(".")
        avg_grade_rounded = round(average)
    else:
        avg_grade = "–"
        avg_grade_rounded = None

    # "Best subject" is ranked by percentage, not by grade (grades round percentages
    # into 5 wide buckets, so several subjects usually tie on grade alone).
    scored_subjects = [row for row in subjects_display if parse_percent_value(row[4]) is not None]
    if scored_subjects:
        best_subject = max(scored_subjects, key=lambda row: parse_percent_value(row[4]))[1]
    elif graded_subjects:
        best_subject = min(graded_subjects, key=lambda row: parse_grade(row[2]))[1]
    else:
        best_subject = "–"

    return {
        "subject_count": len(subjects_display),
        "grade_count": len(znamky),
        "avg_grade": avg_grade,
        "avg_grade_rounded": avg_grade_rounded,
        "best_subject": best_subject,
    }


def split_percentage_and_points(text: str) -> tuple[int, int]:
    """Splits percentage and points from one text (see example from comment below) into tuple

    Args:
        text (str): Text in format XX,X / XX,X (YY,YY%)

    Returns:
        tuple[int, int]: tuple with points and percentage
    """
    # '89,0 / 97,0 (91,75%)'
    points = text[:text.find("(")].strip()
    percentage = text[text.find("(") + 1:text.find(")")].strip()
    return (percentage, points)


def _ensure_student_id(session: requests.Session) -> int | None:
    """Get the cached student id, fetching it from the mainpage if this is
    the first request of the browser session to need it.

    /api/home always populates flask_session_custom["studentId"] as a side
    effect, but /api/portfolio (and, in principle, /api/subject/<id>) can
    fire before the frontend's /api/home call has finished - there's no
    ordering between the two on the client. Without this, that race 401s
    portfolio/subject requests as "not_authenticated" even though the user
    is logged in; the session just hasn't seen the mainpage yet.
    """
    student_id = flask_session_custom.get('studentId')
    if student_id:
        return student_id

    mainpage_response = session.get("https://is.psjg.cz/",
                                    params={"semesterId": flask_session_custom.get("semester")},
                                    headers=headers, timeout=REQUEST_TIMEOUT)
    if mainpage_response.status_code != 200:
        return None
    if 'id="frm-signInForm-name"' in mainpage_response.text:
        flask_session_custom.pop('cookies', None)  # Delete old cookies
        return None

    student_id = get_info(mainpage_response.text)
    flask_session_custom["studentId"] = student_id
    return student_id


def _load_home_data() -> dict:
    """Shared login-session -> dashboard-data pipeline used by both the HTML
    /home route and the JSON /api/home route, so the two never drift apart.

    Returns a dict with "status" of "redirect" (no/expired session), "error"
    (upstream is.psjg.cz failure, carries "code"), or "ok" (carries
    "subjects_display", "csvlist", "stats").
    """
    # Get subjects from saved cookies
    saved_cookies = flask_session_custom.get('cookies')

    if not saved_cookies:
        return {"status": "redirect"}

    session = requests.Session()
    session.verify = certificate
    session.cookies.update(saved_cookies)

    # Read subjects
    mainpage_response = session.get("https://is.psjg.cz/",
                                    params={"semesterId": flask_session_custom.get("semester")},
                                    headers=headers, timeout=REQUEST_TIMEOUT)

    if mainpage_response.status_code != 200:
        return {"status": "error", "code": mainpage_response.status_code}

    if 'id="frm-signInForm-name"' in mainpage_response.text:
        flask_session_custom.pop('cookies', None)  # Delete old cookies
        return {"status": "redirect"}

    student_info = get_info(mainpage_response.text)
    flask_session_custom["studentId"] = student_info

    student_name = get_student_name(mainpage_response.text)
    if student_name:
        flask_session_custom["studentName"] = student_name

    # semesters - and, if nothing was explicitly chosen yet this session,
    # resolve which one is.psjg.cz defaulted to (the <option> it marked
    # selected) so the dropdown reflects the real current semester on first
    # load instead of drifting from whatever data is actually being shown.
    semesters, selected_index = get_semesters(mainpage_response.text)
    flask_session_custom["semesters"] = semesters
    if flask_session_custom.get("semester") is None and selected_index is not None:
        flask_session_custom["semester"] = get_semester_number(semesters[selected_index])

    # Get subjects from HTML response and write them to CSV file
    fieldnames = ["id", "Předmět", "Bodové hodnocení", "Známka", "Výsledná známka"]  # List of column names for CSV file
    subjects = get_csv_subjects(mainpage_response.text, fieldnames).values.tolist()

    responseGrid = session.get("https://is.psjg.cz",
                               params={
                                   "studentScoreGrid-id": 1,
                                   "do": "studentScoreGrid-export",
                                   "semesterId": flask_session_custom.get("semester")
                               },
                               headers=headers, timeout=REQUEST_TIMEOUT)
    if responseGrid.status_code != 200:
        return {"status": "error", "code": responseGrid.status_code}

    df = csv_to_dataframe(text=responseGrid.text)
    znamky = []
    df = df.fillna("")
    csvlist = df.values.tolist()

    # Add grades to csvlist
    for row in csvlist:
        znamky.append(znamka_from_percentage(row[3]))
    df["Znamka"] = znamky
    csvlist = df.values.tolist()

    # id, název, známka, finální známka, body, procenta
    subjects_display = []

    for row in subjects:
        percentage, points = split_percentage_and_points(row[2])
        subjects_display.append([row[0], row[1], row[3], row[4], percentage, points])

    stats = build_home_stats(subjects_display, csvlist)

    return {"status": "ok", "subjects_display": subjects_display, "csvlist": csvlist, "stats": stats}


def _paginate(rows: list, page_arg: int, per_page: int = 10) -> tuple:
    """Clamp page_arg into range and slice rows accordingly.

    Returns (page_slice, current_page, total_pages). total_pages is always
    >= 1 so an empty list still reports "1 / 1" instead of "1 / 0".
    """
    total_pages = max(1, (len(rows) + per_page - 1) // per_page)
    page = min(max(page_arg, 1), total_pages)
    start = (page - 1) * per_page
    return rows[start:start + per_page], page, total_pages


@app.route('/api/session')
def api_session():
    """Whether the browser currently has a valid is.psjg.cz session"""
    return jsonify({"authenticated": bool(flask_session_custom.get('cookies'))})


@app.route('/api/login', methods=["POST"])
def api_login():
    """JSON login endpoint for the React frontend. Sets the same server-side
    session cookie as the HTML login form does.
    """
    payload = request.get_json(silent=True) or request.form
    username = payload.get("username")
    password = payload.get("password")

    if not username or not password:
        return jsonify({"ok": False, "error": "missing_credentials"}), 400

    try:
        session = requests.Session()
        session.verify = certificate
        response = session.post("https://is.psjg.cz/sign/in", data={
            "name": username,
            "password": password,
            "signIn": "Přihlásit se",
            "_do": "signInForm-submit"}, headers=headers, timeout=REQUEST_TIMEOUT)

        if response.status_code != 200:
            return jsonify({"ok": False, "error": "upstream_error", "code": response.status_code}), 502

        if "Neplatné přihlašovací jméno nebo heslo" in response.text:
            return jsonify({"ok": False, "error": "invalid_credentials"}), 401

        flask_session_custom["cookies"] = session.cookies.get_dict()
        return jsonify({"ok": True})

    except requests.exceptions.SSLError:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "ssl_error"}), 502
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        # Backend couldn't reach is.psjg.cz at all (DNS, firewall, proxy, host
        # network policy, ...) or it didn't respond within REQUEST_TIMEOUT -
        # distinct from a bug in this app, and from SSLError above (a
        # ConnectionError subclass, so it must come after it).
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "connection_error"}), 502
    except Exception:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "unknown_error"}), 500


@app.route('/api/logout', methods=["POST"])
def api_logout():
    flask_session_custom.clear()
    return jsonify({"ok": True})


@app.route('/api/semester', methods=["POST"])
def api_semester():
    """Switch the active semester (mirrors the HTML sidenav <select>)."""
    payload = request.get_json(silent=True) or request.form
    label = payload.get("semester")
    if label is None:
        return jsonify({"ok": False, "error": "missing_semester"}), 400
    flask_session_custom["semester"] = get_semester_number(label)
    return jsonify({"ok": True, "selectedSemester": flask_session_custom["semester"]})


@app.route('/api/home')
def api_home():
    """JSON version of /home for the React dashboard."""
    if not flask_session_custom.get('cookies'):
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    try:
        result = _load_home_data()
    except requests.exceptions.SSLError:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "ssl_error"}), 502
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "connection_error"}), 502
    except Exception:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "unknown_error"}), 500

    if result["status"] == "redirect":
        return jsonify({"ok": False, "error": "not_authenticated"}), 401
    if result["status"] == "error":
        return jsonify({"ok": False, "error": "upstream_error", "code": result["code"]}), 502

    grades_page, page, total_pages = _paginate(result["csvlist"], request.args.get('page', 1, type=int))

    return jsonify({
        "ok": True,
        "subjects": [
            {"id": r[0], "name": r[1], "knownGrade": r[2], "finalGrade": r[3], "percentage": r[4], "points": r[5]}
            for r in result["subjects_display"]
        ],
        "grades": [
            {"date": r[0], "name": r[1], "subject": r[2], "percentage": r[3], "points": r[4], "grade": r[6] if len(r) > 6 else None}
            for r in grades_page
        ],
        "page": {"current": page, "total": total_pages},
        "stats": result["stats"],
        "semesters": [{"index": i, "label": label} for i, label in enumerate(flask_session_custom.get("semesters", []))],
        "selectedSemester": flask_session_custom.get("semester", -1),
        "studentName": flask_session_custom.get("studentName"),
    })


def _load_subject_data(subject_id) -> dict:
    """Shared pipeline for /subject/<id> and /api/subject/<id>."""
    saved_cookies = flask_session_custom.get('cookies')

    if not saved_cookies:
        return {"status": "redirect"}

    session = requests.Session()
    session.verify = certificate
    session.cookies.update(saved_cookies)

    student_id = _ensure_student_id(session)
    if not student_id:
        return {"status": "redirect"}

    response = session.get("https://is.psjg.cz/student/student-exam-overview",
                           params={
                               "studentExamOverview-examGrid-id": "1",
                               "studentId": student_id,
                               "subjectId": subject_id,
                               "do": "studentExamOverview-examGrid-export",
                               "semesterId": flask_session_custom.get("semester")
                           }, headers=headers, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        return {"status": "error", "code": response.status_code}

    if 'id="frm-signInForm-name"' in response.text:
        flask_session_custom.pop('cookies', None)  # Delete old cookies
        return {"status": "redirect"}

    df = csv_to_dataframe(text=response.text)

    znamky = []
    csvlist = df.values.tolist()

    # Add znamka to csvlist
    for x, row in enumerate(csvlist):
        znamky.append(znamka_from_percentage(row[5]))
    df["Znamka"] = znamky
    df = df.fillna("")
    csvlist = df.values.tolist()

    return {"status": "ok", "csvlist": csvlist}


@app.route('/api/subject/<subject_id>')
def api_subject(subject_id: int):
    """JSON version of /subject/<id> for the React dashboard."""
    if not flask_session_custom.get('cookies'):
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    try:
        result = _load_subject_data(subject_id)
    except requests.exceptions.SSLError:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "ssl_error"}), 502
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "connection_error"}), 502
    except Exception:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "unknown_error"}), 500

    if result["status"] == "redirect":
        return jsonify({"ok": False, "error": "not_authenticated"}), 401
    if result["status"] == "error":
        return jsonify({"ok": False, "error": "upstream_error", "code": result["code"]}), 502

    return jsonify({
        "ok": True,
        "grades": [
            {"date": r[0], "name": r[1], "points": r[4], "percentage": r[5], "description": r[6], "grade": r[7] if len(r) > 7 else None}
            for r in result["csvlist"]
        ],
    })


def _load_portfolio_data() -> dict:
    """Shared pipeline for /portfolio and /api/portfolio."""
    saved_cookies = flask_session_custom.get('cookies')

    if not saved_cookies:
        return {"status": "redirect"}

    session = requests.Session()
    session.verify = certificate
    session.cookies.update(saved_cookies)

    student_id = _ensure_student_id(session)
    if not student_id:
        return {"status": "redirect"}

    # semesterId here is a best-effort guess at consistency with every other
    # endpoint in this app (mainpage, grades export, exam overview all take
    # it) - unverified against a real is.psjg.cz response since this app has
    # no way to check that from here, but harmless if the achievement page
    # ignores it.
    response = session.get(f"https://is.psjg.cz/achievement/view/{student_id}",
                           params={"semesterId": flask_session_custom.get("semester")},
                           headers=headers, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        return {"status": "error", "code": response.status_code}

    if 'id="frm-signInForm-name"' in response.text:
        flask_session_custom.pop('cookies', None)  # Delete old cookies
        return {"status": "redirect"}

    return {"status": "ok", "portfolio": get_portfolio(text=response.text)}


@app.route('/api/portfolio')
def api_portfolio():
    """JSON version of /portfolio for the React dashboard."""
    if not flask_session_custom.get('cookies'):
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    try:
        result = _load_portfolio_data()
    except requests.exceptions.SSLError:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "ssl_error"}), 502
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "connection_error"}), 502
    except Exception:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "unknown_error"}), 500

    if result["status"] == "redirect":
        return jsonify({"ok": False, "error": "not_authenticated"}), 401
    if result["status"] == "error":
        return jsonify({"ok": False, "error": "upstream_error", "code": result["code"]}), 502

    return jsonify({"ok": True, **result["portfolio"]})

def _load_zkouseni_data() -> dict:
    """Shared pipeline for /api/zkouseni.

    No studentId needed here (unlike portfolio/subject) - confirmed live
    that /exam/student-view is scoped to the logged-in session directly.
    """
    saved_cookies = flask_session_custom.get('cookies')
    if not saved_cookies:
        return {"status": "redirect"}

    session = requests.Session()
    session.verify = certificate
    session.cookies.update(saved_cookies)

    response = session.get("https://is.psjg.cz/exam/student-view",
                           params={"semesterId": flask_session_custom.get("semester")},
                           headers=headers, timeout=REQUEST_TIMEOUT)

    if response.status_code != 200:
        return {"status": "error", "code": response.status_code}

    if 'id="frm-signInForm-name"' in response.text:
        flask_session_custom.pop('cookies', None)  # Delete old cookies
        return {"status": "redirect"}

    return {"status": "ok", "exams": get_exams(response.text)}


@app.route('/api/zkouseni')
def api_zkouseni():
    """JSON endpoint for Zkoušení (oral exam schedule)."""
    if not flask_session_custom.get('cookies'):
        return jsonify({"ok": False, "error": "not_authenticated"}), 401

    try:
        result = _load_zkouseni_data()
    except requests.exceptions.SSLError:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "ssl_error"}), 502
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "connection_error"}), 502
    except Exception:
        print(traceback.format_exc())
        return jsonify({"ok": False, "error": "unknown_error"}), 500

    if result["status"] == "redirect":
        return jsonify({"ok": False, "error": "not_authenticated"}), 401
    if result["status"] == "error":
        return jsonify({"ok": False, "error": "upstream_error", "code": result["code"]}), 502

    return jsonify({"ok": True, "exams": result["exams"]})


# --- React frontend (ispsjginjs), built into FRONTEND_DIST at image build time ---

FRONTEND_DIST = os.environ.get("FRONTEND_DIST") or os.path.join(os.path.dirname(__file__), "frontend_dist")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    """Serves the built React app, falling back to index.html for any path
    that isn't a real built asset - the client-side router (react-router)
    then takes over from there. /api/* never reaches this: Flask matches
    those routes first regardless of definition order.
    """
    if not os.path.isdir(FRONTEND_DIST):
        # Normal for a plain local checkout: frontend_dist/ only exists inside
        # the Docker image (built from ispsjginjs at image build time). For
        # local dev, run the two apps separately instead - `npm run dev` in
        # ispsjginjs, which proxies /api/* to this Flask server (see its
        # vite.config.js) - rather than expecting this route to serve the UI.
        return (
            "frontend_dist/ not found. This route serves the built React app "
            "(see the ispsjginjs repo), which only exists inside the Docker "
            "image. For local development, run `npm run dev` in ispsjginjs "
            "instead - it proxies /api/* to this server.",
            200,
        )
    target = os.path.join(FRONTEND_DIST, path) if path else None
    if target and os.path.isfile(target):
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, "index.html")


if __name__ == "__main__":
    app.run(debug=(os.environ.get('DEBUG') == 'True'))
