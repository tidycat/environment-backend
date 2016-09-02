import BaseHTTPServer
import sys
import time
import json
import os
import logging
import re
from environment_backend.entrypoint import handler


HOST_NAME = sys.argv[1]
PORT_NUMBER = int(sys.argv[2])
logger = logging.getLogger("environment_backend")

allowed_headers = [
    "Content-Type",
    "Authorization"
]

allowed_methods = [
    "OPTIONS",
    "GET",
    "POST",
    "PATCH",
    "DELETE"
]


class LocalEnvironmentBackend(BaseHTTPServer.BaseHTTPRequestHandler):

    server_version = "LocalEnvironmentBackend/0.1"

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header("Access-Control-Allow-Methods", ",".join(allowed_methods))  # NOQA
        self.send_header("Access-Control-Allow-Headers", ",".join(allowed_headers))  # NOQA
        self.end_headers()

    def do_GET(self):
        status, result = handle_request({}, self.headers, self.path, "GET")
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header("Access-Control-Allow-Methods", ",".join(allowed_methods))  # NOQA
        self.send_header("Access-Control-Allow-Headers", ",".join(allowed_headers))  # NOQA
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result))

    def do_PATCH(self):
        length = int(self.headers['Content-Length'])
        patch_data = self.rfile.read(length)
        payload = json.loads(patch_data)
        status, result = handle_request(
            payload,
            self.headers,
            self.path,
            "PATCH"
        )
        self.send_response(status)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header("Access-Control-Allow-Methods", ",".join(allowed_methods))  # NOQA
        self.send_header("Access-Control-Allow-Headers", ",".join(allowed_headers))  # NOQA
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result))


def handle_request(payload, headers, resource_path, http_method):
    userid = None
    user_id_path = re.match('^/environment/settings/([0-9]+)$', resource_path)  # NOQA
    if user_id_path:
        resource_path = "/environment/settings/{userid}"
        userid = user_id_path.group(1)

    event = {
        "resource-path": resource_path,
        "payload": payload,
        "http-method": http_method,
        "jwt_signing_secret": "supersekr3t",
        "bearer_token": headers.get("Authorization"),
        "environment_dynamodb_endpoint_url": os.environ['DYNAMODB_ENDPOINT_URL'],  # NOQA
        "environment_dynamodb_table_name": "%s_environment" % os.environ['DYNAMODB_TABLE_NAME_PREFIX'],  # NOQA
        "userid": userid,
    }
    try:
        response_payload = handler(event, {})
        logger.debug("Server Response: %s" % response_payload)
        return transform_response(response_payload)
    except TypeError as e:
        logger.debug("Server error Response: %s" % str(e))
        return transform_response(json.loads(str(e)))


def transform_response(response_payload):
    status = response_payload['http_status']
    data = response_payload['data']
    return (status, data)


if __name__ == '__main__':
    server_class = BaseHTTPServer.HTTPServer
    httpd = server_class((HOST_NAME, PORT_NUMBER), LocalEnvironmentBackend)
    print(time.asctime(), "Server Starts - %s:%s" % (HOST_NAME, PORT_NUMBER))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    print(time.asctime(), "Server Stops - %s:%s" % (HOST_NAME, PORT_NUMBER))
