import requests
import json
from flask import Flask, jsonify, request, abort
import logging
import re
from urllib.parse import unquote

app = Flask(__name__)

# Proxy configuration

headers = {
    # this is internal ID of an instegram backend app. It doesn't change often.
    "x-ig-app-id": "936619743392459",
    # use browser-like features
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/62.0.3202.94 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "*/*",
}
proxy = "http://44eb11bd6211d97f3a8c:238a8098f45633f3@gw.dataimpulse.com:823"
proxies = {
    "http": proxy,
    "https": proxy
}

logging.basicConfig(level=logging.INFO)

# Example usage:
def scrape_user(username: str) -> dict:
    # Instagram usernames: 1-30 chars, letters, numbers, periods, underscores
    if not re.match(r'^[A-Za-z0-9._]{1,30}$', username):
        logging.warning(f"Invalid username: {username}")
        return None
    try:
        response = requests.get(
            f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
            headers=headers, proxies=proxies, timeout=10
        )
        response.raise_for_status()
        data = json.loads(response.content)
        data = data["data"]["user"]
        return parse_user(data)
    except requests.RequestException as e:
        logging.error(f"Network error for user {username}: {e}")
        return None
    except (KeyError, json.JSONDecodeError) as e:
        logging.error(f"Parsing error for user {username}: {e}")
        return None
        



def parse_user(data: dict) -> dict:
    """Parse instagram user's hidden web dataset for user's data"""
    # Helper to safely get nested values
    def get_nested(d, keys, default=None):
        for key in keys:
            if isinstance(d, dict):
                d = d.get(key, default)
            else:
                return default
        return d

    # Extract bio_links
    bio_links = [link.get('url') for link in data.get('bio_links', [])]
    # Extract videos
    videos = []
    for edge in get_nested(data, ['edge_felix_video_timeline', 'edges'], []):
        node = edge.get('node', {})
        videos.append({
            'id': node.get('id'),
            'title': node.get('title'),
            'shortcode': node.get('shortcode'),
            'thumb': node.get('display_url'),
            'url': node.get('video_url'),
            'views': node.get('video_view_count'),
            'tagged': [tag.get('node', {}).get('user', {}).get('username') for tag in node.get('edge_media_to_tagged_user', {}).get('edges', [])],
            'captions': [cap.get('node', {}).get('text') for cap in node.get('edge_media_to_caption', {}).get('edges', [])],
            'comments_count': get_nested(node, ['edge_media_to_comment', 'count']),
            'comments_disabled': node.get('comments_disabled'),
            'taken_at': node.get('taken_at_timestamp'),
            'likes': get_nested(node, ['edge_liked_by', 'count']),
            'location': get_nested(node, ['location', 'name']),
            'duration': node.get('video_duration'),
        })
    # Extract images (same structure as videos)
    images = []
    for edge in get_nested(data, ['edge_felix_video_timeline', 'edges'], []):
        node = edge.get('node', {})
        images.append({
            'id': node.get('id'),
            'title': node.get('title'),
            'shortcode': node.get('shortcode'),
            'src': node.get('display_url'),
            'url': node.get('video_url'),
            'views': node.get('video_view_count'),
            'tagged': [tag.get('node', {}).get('user', {}).get('username') for tag in node.get('edge_media_to_tagged_user', {}).get('edges', [])],
            'captions': [cap.get('node', {}).get('text') for cap in node.get('edge_media_to_caption', {}).get('edges', [])],
            'comments_count': get_nested(node, ['edge_media_to_comment', 'count']),
            'comments_disabled': node.get('comments_disabled'),
            'taken_at': node.get('taken_at_timestamp'),
            'likes': get_nested(node, ['edge_liked_by', 'count']),
            'location': get_nested(node, ['location', 'name']),
            'accesibility_caption': node.get('accessibility_caption'),
            'duration': node.get('video_duration'),
        })
    # Extract related profiles
    related_profiles = [edge.get('node', {}).get('username') for edge in get_nested(data, ['edge_related_profiles', 'edges'], [])]

    result = {
        "name": data.get("full_name"),
        "username": data.get("username"),
        "id": data.get("id"),
        "category": data.get("category_name"),
        "business_category": data.get("business_category_name"),
        "phone": data.get("business_phone_number"),
        "email": data.get("business_email"),
        "bio": data.get("biography"),
        "bio_links": bio_links,
        "homepage": data.get("external_url"),
        "followers": get_nested(data, ["edge_followed_by", "count"]),
        "followings": get_nested(data, ["edge_follow", "count"]),
        "facebook_id": data.get("fbid"),
        "is_private": data.get("is_private"),
        "is_verified": data.get("is_verified"),
        "profile_image": data.get("profile_pic_url_hd"),
        "video_count": get_nested(data, ["edge_felix_video_timeline", "count"]),
        "videos": videos,
        "image_count": get_nested(data, ["edge_owner_to_timeline_media", "count"]),
        "images": images,
        "saved_count": get_nested(data, ["edge_saved_media", "count"]),
        "collections_count": get_nested(data, ["edge_saved_media", "count"]),
        "related_profiles": related_profiles,
    }

    # Return only selected fields as before
    return {
        "name": result["name"],
        "username": result["username"],
        "id": result["id"],
        "followers": result["followers"],
        "followings": result["followings"],
        "is_private": result["is_private"],
        "is_verified": result["is_verified"],
        "profile_image": result["profile_image"],
        "bio": result["bio"],
        "posts": result['image_count']
    }


@app.route('/scrape_user/<username>', methods=['GET'])
def scrape_user_api(username):
    logging.info(f"Request for username: {username}")
    result = scrape_user(username)
    if result is None:
        abort(404, description="User not found or error occurred.")
    return jsonify(result), 200

@app.route('/proxy-image')
def proxy_image():
    instagram_url = request.args.get('url')
    print(f"Requested URL: {instagram_url}")

    try:
        response = requests.get(instagram_url, stream=True)
        response.raise_for_status()

        return Response(
            response.iter_content(chunk_size=1024),
            content_type=response.headers['Content-Type']
        )
    except requests.RequestException as e:
        return f"Failed to fetch image: {e}", 500
