from httpx import AsyncClient


async def test_root_describes_the_service(client: AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "watchlog API",
        "version": "0.1.0",
        "docs": "/api/docs",
    }


async def test_openapi_and_docs_are_available_in_dev(client: AsyncClient) -> None:
    openapi = await client.get("/api/openapi.json")
    docs = await client.get("/api/docs")

    assert openapi.status_code == 200
    assert openapi.json()["info"]["title"] == "watchlog API"
    assert docs.status_code == 200
    assert "text/html" in docs.headers["content-type"]
