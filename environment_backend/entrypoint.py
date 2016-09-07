import logging
from environment_backend.user_environment import UserEnvironment
from environment_backend.http import format_response
from environment_backend.http import format_error_payload

__version__ = "0.0.1"
logging.basicConfig()
logger = logging.getLogger("environment_backend")
logger.setLevel(logging.DEBUG)


def handler(event, context):
    logger.debug("Received event: %s" % event)

    resource_path = event.get('resource-path')
    http_method = event.get('http-method')

    if http_method == "GET" and resource_path == "/environment/settings/{userid}":  # NOQA
        logger.debug("Getting settings for user: %s" % event.get('userid'))
        t = UserEnvironment(event)
        return t.process_user_event("find_settings")

    elif http_method == "PATCH" and resource_path == "/environment/settings/{userid}":  # NOQA
        logger.debug("Updating user: %s" % event.get('userid'))
        t = UserEnvironment(event)
        return t.process_user_event("update_settings")

    elif http_method == "GET" and resource_path == "/environment/ping":
        payload = {
            "data": [],
            "meta": {
                "version": __version__
            }
        }
        return format_response(200, payload)

    payload = format_error_payload(400, "Invalid path %s" % resource_path)
    return format_response(400, payload)
