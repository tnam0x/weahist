import httpx
import respx

from weahist.clients.base import HttpClient
from weahist.clients.geocoding import GeocodingClient


@respx.mock
def test_geocode_returns_first_result(settings) -> None:
    respx.get(settings.geocoding_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "name": "Hanoi",
                        "latitude": 21.0285,
                        "longitude": 105.8542,
                        "country": "Vietnam",
                        "timezone": "Asia/Ho_Chi_Minh",
                    }
                ]
            },
        )
    )
    with HttpClient(settings) as http:
        loc = GeocodingClient(http, settings).geocode("Hanoi")
    assert loc.name == "Hanoi"
    assert loc.country == "Vietnam"
    assert loc.timezone == "Asia/Ho_Chi_Minh"
    assert loc.latitude == 21.0285


@respx.mock
def test_geocode_no_results(settings) -> None:
    respx.get(settings.geocoding_url).mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    with HttpClient(settings) as http:
        client = GeocodingClient(http, settings)
        try:
            client.geocode("nowhere-xyzzy")
        except Exception as exc:
            assert "no geocoding results" in str(exc)
        else:
            raise AssertionError("expected GeocodingError")
