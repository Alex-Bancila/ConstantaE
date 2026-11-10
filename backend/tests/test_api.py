from app.schemas import AnalysisResponse


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_analyze_returns_all_three_results(client, example_page):
    response = client.post("/analyze", json=example_page)

    assert response.status_code == 200
    result = AnalysisResponse.model_validate(response.json())
    assert result.status == "done"
    assert len(result.images) == len(example_page["images"])
    assert result.trust is not None
    assert result.legal is not None


def test_response_uses_camel_case(client, example_page):
    body = client.post("/analyze", json=example_page).json()

    assert "analysisId" in body
    assert "aiProbability" in body["images"][0]


def test_get_analysis_returns_saved_result(client, example_page):
    created = client.post("/analyze", json=example_page).json()

    fetched = client.get(f"/analyze/{created['analysisId']}")

    assert fetched.status_code == 200
    assert fetched.json() == created


def test_get_unknown_analysis_is_404(client):
    assert client.get("/analyze/does-not-exist").status_code == 404
