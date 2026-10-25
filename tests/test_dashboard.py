import pytest
from src.app import create_app

@pytest.fixture
def client():
    app = create_app('default')
    app.testing = True
    with app.test_client() as client:
        yield client

def test_dashboard_page(client):
    response = client.get('/dashboard/')
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'Cluster Dashboard' in html
    assert 'HDFS Storage' in html
    assert 'Recent MapReduce Jobs' in html

def test_dashboard_hdfs_api_error_handling(client, monkeypatch):
    def mock_check_output(*args, **kwargs):
        raise Exception('simulated command failure')
    monkeypatch.setattr('subprocess.check_output', mock_check_output)
    resp = client.get('/dashboard/api/hdfs/overview')
    assert resp.status_code == 500
    json_data = resp.get_json()
    assert 'error' in json_data
