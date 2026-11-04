from app import app


def test_get_order():
    resp = app.test_client().get("/orders/7")
    assert resp.json == {"id": 7, "status": "shipped"}
