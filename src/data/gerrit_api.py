# Gerrit API底层请求与数据处理

import os
import json
import logging
import requests
from typing import Dict, Any

# 建议从utils.logger导入logger
from utils.logger import logger

def make_gerrit_rest_request(ctx, endpoint: str) -> Dict[str, Any]:
    """Make a REST API request to Gerrit and handle the response"""
    logger.info(f"[gerrit_api] make_gerrit_rest_request called with endpoint={endpoint}")
    gerrit_ctx = ctx.request_context.lifespan_context
    
    if not gerrit_ctx.http_password:
        logger.error("[gerrit_api] HTTP password not set in context")
        raise ValueError("HTTP password not set. Please set GERRIT_HTTP_PASSWORD in your environment.")
        
    # Ensure endpoint starts with 'a/' for authenticated requests
    if not endpoint.startswith('a/'):
        endpoint = f'a/{endpoint}'
    
    # Check if host already contains protocol prefix
    if gerrit_ctx.host.startswith(('http://', 'https://')):
        url = f"{gerrit_ctx.host}/{endpoint}"
    else:
        url = f"https://{gerrit_ctx.host}/{endpoint}"
    
    auth = requests.auth.HTTPBasicAuth(gerrit_ctx.user, gerrit_ctx.http_password)
    
    try:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'GerritReviewMCP/1.0'
        }
        logger.info(f"[gerrit_api] Sending GET request to: {url}")
        verify = os.getenv("GERRIT_VERIFY_SSL", "True").lower() != "false"
        response = requests.get(url, auth=auth, headers=headers, verify=verify)
        logger.info(f"[gerrit_api] Received response: status_code={response.status_code}")
        
        if response.status_code == 401:
            logger.error(f"[gerrit_api] Authentication failed for user '{gerrit_ctx.user}' at '{url}'. Response: {response.text}")
            logger.error(f"Response: {response.text}")
            raise Exception("Authentication failed. Please check your Gerrit HTTP password in your account settings.")
        
        response.raise_for_status()
        
        content = response.text
        if content.startswith(")]}'"):
            content = content[4:]
        
        try:
            result = json.loads(content)
            logger.info(f"[gerrit_api] Successfully parsed JSON response for endpoint={endpoint}")
            return result
        except json.JSONDecodeError as e:
            logger.error(f"[gerrit_api] Failed to parse JSON response: {str(e)}")
            raise Exception(f"Failed to parse Gerrit response as JSON: {str(e)}")
        
    except requests.exceptions.RequestException as e:
        logger.error(f"[gerrit_api] REST request failed: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"[gerrit_api] Response status: {e.response.status_code}")
        raise Exception(f"Failed to make Gerrit REST API request: {str(e)}")

    return {} 