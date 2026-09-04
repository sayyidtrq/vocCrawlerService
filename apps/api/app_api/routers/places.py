from __future__ import annotations

import httpx

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.config import get_settings
from apps.api.app_api.service_auth import ServicePrincipal, require_service_principal

router = APIRouter(prefix="/places", tags=["places"])

class PlaceResolveResponse(BaseModel):
    external_place_id: str
    hospital_name: str | None = None
    address: str | None = None
    google_maps_url: str | None = None

@router.get(
    "/resolve",
    response_model=PlaceResolveResponse,
    summary="Resolve koordinat → Google place_id",
    description="Mengubah lat/lng menjadi `external_place_id` (Google) beserta nama & alamat via Google Maps API. Butuh `GOOGLE_MAPS_API_KEY` di server.",
)
async def resolve_place_id(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    principal: ServicePrincipal = Depends(require_service_principal),
):
    settings = get_settings()
    if not settings.google_maps_api_key:
        raise HTTPException(
            status_code=500, detail="Google Maps API Key not configured."
        )

    # Use Google Maps Geocoding API to resolve coordinates to a place
    # Note: Reverse geocoding usually returns multiple results, we take the most specific one.
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "latlng": f"{lat},{lng}",
        "key": settings.google_maps_api_key,
        "language": settings.google_places_language_code,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Error reaching Google Maps API")
        
    data = response.json()
    google_status = data.get("status")
    if google_status != "OK" or not data.get("results"):
        error_msg = data.get("error_message", "Place not found for these coordinates")
        raise HTTPException(
            status_code=404 if google_status == "ZERO_RESULTS" else 400,
            detail=f"Google API Error: {google_status}. Detail: {error_msg}"
        )
        
    result = data["results"][0]
    place_id = result.get("place_id")
    address = result.get("formatted_address")
    
    # We can try to extract a name if it's a POI, but Geocoding might just give addresses.
    # To get a name and URL properly, we'd query the Places Details API next.
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    details_params = {
        "place_id": place_id,
        "fields": "name,url",
        "key": settings.google_maps_api_key,
        "language": settings.google_places_language_code,
    }
    
    async with httpx.AsyncClient() as client:
        details_response = await client.get(details_url, params=details_params)
        
    details_data = details_response.json()
    name = None
    google_maps_url = None
    if details_data.get("status") == "OK":
        name = details_data["result"].get("name")
        google_maps_url = details_data["result"].get("url")
        
    return PlaceResolveResponse(
        external_place_id=place_id,
        hospital_name=name,
        address=address,
        google_maps_url=google_maps_url
    )
