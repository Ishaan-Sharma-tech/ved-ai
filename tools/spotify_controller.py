TOOL_NAME = "spotify_controller"
TOOL_DESCRIPTION = "A tool to pause or play music via the Spotify Web API"

import logging
import json
import os
import requests

logger = logging.getLogger("aether.spotify_controller")

async def run(**kwargs):
    # Extract args safely
    current_volume = None
    try:
        current_volume = int(kwargs.get("current_volume"))
    except (KeyError, ValueError):
        logger.warning("Volume not provided or not a valid integer.")

    device_id = kwargs.get("device_id")
    if not device_id:
        logger.error("Device ID is required.")
        return "Error: Device ID is required."

    api_key = os.environ.get("SPOTIFY_API_KEY_HERE")
    if not api_key:
        logger.error("SPOTIFY_API_KEY_HERE not found in environment variables.")
        return "Error: SPOTIFY_API_KEY_HERE not found in environment variables."

    api_url = f"https://api.spotify.com/v1/me/player"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Get current player status
    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        logger.error(f"Failed to get current player status. Status code: {response.status_code}")
        return f"Error: Failed to get current player status. Status code: {response.status_code}"

    data = response.json()
    current_status = data["is_playing"]
    current_volume = data["device"]["volume_percent"]

    # Check if device_id is valid
    if current_status and data["device"]["id"] != device_id:
        logger.error("Device ID does not match the one in the current player status.")
        return "Error: Device ID does not match the one in the current player status."

    # Pause or play music
    if current_status:
        play_response = requests.put(f"{api_url}/pause", headers=headers)
        if play_response.status_code != 200:
            logger.error(f"Failed to pause music. Status code: {play_response.status_code}")
            return f"Error: Failed to pause music. Status code: {play_response.status_code}"
    else:
        play_response = requests.put(f"{api_url}/play", headers=headers)
        if play_response.status_code != 200:
            logger.error(f"Failed to play music. Status code: {play_response.status_code}")
            return f"Error: Failed to play music. Status code: {play_response.status_code}"

    # Update volume
    if current_volume != kwargs.get("current_volume"):
        update_volume_response = requests.put(f"{api_url}/volume", headers=headers, json={"volume_percent": kwargs.get("current_volume")})
        if update_volume_response.status_code != 200:
            logger.error(f"Failed to update volume. Status code: {update_volume_response.status_code}")
            return f"Error: Failed to update volume. Status code: {update_volume_response.status_code}"

    return "Music paused or played successfully."