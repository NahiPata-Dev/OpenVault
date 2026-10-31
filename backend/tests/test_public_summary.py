from app.seed import RESOURCE_IDS
from tests.conftest import login


def test_public_summary_contains_only_sample_city_and_category_aggregates(client):
    response = client.get("/api/public/summary")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"cities", "categories"}
    assert len(body["cities"]) == 7
    assert set(body["categories"]) == {
        "aerial robotics",
        "cnc machining",
        "compute",
        "electronics",
        "electronics library",
        "electrical testing",
        "energy",
        "equipment",
        "fluid dynamics",
        "fabrication",
        "immersive media",
        "laser cutting",
        "learning space",
        "media production",
        "mechanical testing",
        "media",
        "microscopy",
        "space",
        "3d scanning",
    }
    assert {
        city["city"]: (city["resource_count"], city["organization_count"])
        for city in body["cities"]
    } == {
        "Bengaluru": (3, 1),
        "Chennai": (3, 1),
        "Delhi NCR": (3, 1),
        "Hyderabad": (9, 2),
        "Kolkata": (3, 1),
        "Mumbai": (3, 1),
        "Pune": (3, 1),
    }
    assert all(
        set(city) == {"city", "resource_count", "organization_count"}
        for city in body["cities"]
    )
    serialized = response.text.casefold()
    assert not any(
        private_field in serialized
        for private_field in ("email", "booking", "requester", "display_name", "user_id")
    )


def test_resource_endpoints_require_login_and_return_organization_profile(client):
    assert client.get("/api/resources").status_code == 401
    assert client.get(
        f"/api/resources/{RESOURCE_IDS['camera']}"
    ).status_code == 401

    login(client, "requester_a")
    listing = client.get("/api/resources")
    assert listing.status_code == 200, listing.text
    camera = next(
        item
        for item in listing.json()["items"]
        if item["id"] == RESOURCE_IDS["camera"]
    )
    assert camera["organization_name"] == "Northstar Engineering Lab (Sample)"
    assert camera["organization_type"] == "Engineering lab"
    assert camera["city"] == "Hyderabad"
    assert camera["area"] == "Gachibowli"
    assert camera["id_required"] == "Institution ID card"

    detail = client.get(f"/api/resources/{RESOURCE_IDS['camera']}")
    assert detail.status_code == 200, detail.text
    profile = detail.json()["resource"]
    assert profile["organization_name"] == camera["organization_name"]
    assert profile["organization_type"] == camera["organization_type"]
    assert profile["city"] == camera["city"]
    assert profile["area"] == camera["area"]
    assert profile["id_required"] == camera["id_required"]


def test_public_summary_is_rate_limited_per_client(client):
    for _ in range(60):
        response = client.get("/api/public/summary")
        assert response.status_code == 200, response.text

    limited = client.get("/api/public/summary")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
