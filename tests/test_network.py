from app import certificates, certificate_chain_path
import requests


def test_certificate_check():
    certificates()
    try:
        response = requests.get("https://is.psjg.cz", verify=certificate_chain_path)
        assert response.status_code == 200
        assert True, "Certificate is valid and connection is successful."
    except requests.exceptions.SSLError as e:
        assert False, f"SSL Error: {e}"
    except Exception as e:
        assert False, f"Unexpected error: {e}"
