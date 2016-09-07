import logging
from boto3.exceptions import Boto3Error
from botocore.exceptions import ClientError
from botocore.exceptions import BotoCoreError
from boto3.dynamodb.conditions import Key
from environment_backend.http import format_response
from environment_backend.http import validate_jwt
from environment_backend.http import format_error_payload
from environment_backend.http import dynamodb_results
from environment_backend.http import dynamodb_update_item


logger = logging.getLogger("environment_backend")


class UserEnvironment(object):

    def __init__(self, lambda_event):
        for prop in ["payload",
                     "jwt_signing_secret",
                     "bearer_token",
                     "environment_dynamodb_endpoint_url",
                     "environment_dynamodb_table_name"]:
            setattr(self, prop, lambda_event.get(prop))
            self.token = None
            self.userid = None
            self.resource_path = lambda_event.get('resource-path', "")
            self.path_settingsid = lambda_event.get('userid', '0')

    def process_user_event(self, method_name):
        self.token = validate_jwt(self.bearer_token, self.jwt_signing_secret)
        if not self.token:
            error_msg = "Invalid JSON Web Token"
            logger.info(error_msg)
            return format_response(401, format_error_payload(401, error_msg))

        try:
            self.path_settingsid = int(self.path_settingsid)
        except ValueError:
            error_msg = "Invalid userid path %s" % self.path_settingsid
            logger.info(error_msg)
            return format_response(401, format_error_payload(401, error_msg))

        try:
            self.userid = int(self.token.get('sub'))
        except ValueError:
            error_msg = "Invalid sub field in JWT"
            logger.info(error_msg)
            return format_response(401, format_error_payload(401, error_msg))

        if not self.userid == self.path_settingsid:
            error_msg = "Not authorized to access account %s" % self.path_settingsid  # NOQA
            logger.info(error_msg)
            return format_response(401, format_error_payload(401, error_msg))

        method_to_call = getattr(self, method_name)
        return method_to_call()

    def find_settings(self):
        result = {}
        try:
            results = dynamodb_results(
                self.environment_dynamodb_endpoint_url,
                self.environment_dynamodb_table_name,
                Key('user_id').eq(self.userid)
            )
            # There should really only be one result
            result = results.next()
        except (Boto3Error, BotoCoreError, ClientError) as e:
            error_msg = "Error querying for user %s from the datastore" % self.userid  # NOQA
            logger.error("%s: %s" % (error_msg, str(e)))
            return format_response(500, format_error_payload(500, error_msg))
        except StopIteration:
            pass

        payload = {
            "data": {
                "type": "settings",
                "id": self.userid,
                "relationships": {
                    "saved-filters": {
                        "data": []
                    }
                }
            },
            "included": []
        }

        # e.g. result = { "filter1":["tag1", "tag2", "tagn"], "filter2": ["tag1", "tagn"]}  # NOQA
        filters = result.get('saved_filters')
        logger.debug("filters is %s" % filters)
        if not filters:
            # The case where this is a brand new user with no previous filters
            filters = {}

        filterArr = []
        for key, value in filters.iteritems():
            record = {
                "id": key,
                "type": "saved-filter",
                "attributes": {
                    "tags": value
                }
            }
            filterArr.append(record)
        payload['data']['relationships']['saved-filters']['data'] = filterArr
        payload['included'] = filterArr
        return format_response(200, payload)

    def update_settings(self):
        patch_data = self.payload.get('data', {})
        # patch_relationships = self.payload.get('relationships', {})

        logger.debug("patch data is %s" % patch_data)
        # logger.debug("patch relationships is %s" % patch_relationships)

        # The PATCH payload needs to have the 'type' member
        patch_type = patch_data.get('type')
        if patch_type != "settings":
            error_msg = "Invalid 'type' member, should be 'settings'"
            logger.info(error_msg)
            return format_response(400, format_error_payload(400, error_msg))

        # The PATCH payload needs to have the 'id' member
        try:
            m_user_id = int(patch_data.get('id'))
            if m_user_id != self.userid:
                raise ValueError
        except ValueError:
            error_msg = "Invalid 'id' member, should match patch url"
            logger.info(error_msg)
            return format_response(400, format_error_payload(400, error_msg))

        # Gather the attributes that need to be updated
        saved_filters = patch_data.get('relationships', {}).get('saved-filters', {}).get('data', [])  # NOQA
        logger.debug("saved filters is %s" % saved_filters)
        # if not saved_filters:
        #     payload = {
        #         "meta": {
        #             "message": "Nothing to do here!"
        #         }
        #     }
        #     return format_response(204, payload)

        # Collate the specified saved filters
        saved_filters_obj_to_persist = {}
        for m_filter in saved_filters:
            logger.debug("this saved filter is: %s" % m_filter)
            name = m_filter.get('id')
            tags = m_filter.get('attributes', {}).get('tags', [])
            logger.debug("this saved name is: %s" % name)
            logger.debug("this saved tags are: %s" % tags)
            saved_filters_obj_to_persist.update({name: tags})
        logger.debug("object to persist is: %s" % saved_filters_obj_to_persist)

        # Overwrite the record in the datastore with these values
        key = {
            "user_id": self.userid
        }
        values = {
            ":f": saved_filters_obj_to_persist
        }
        update_expression = "set saved_filters=:f"
        try:
            dynamodb_update_item(
                endpoint_url=self.environment_dynamodb_endpoint_url,
                table_name=self.environment_dynamodb_table_name,
                key=key,
                update_expression=update_expression,
                expr_attribute_values=values
            )
        except (Boto3Error, BotoCoreError, ClientError) as e:
            error_msg = "Error updating user %s in the datastore" % self.userid
            logger.error("%s: %s" % (error_msg, str(e)))
            return format_response(500, format_error_payload(500, error_msg))

        payload = {
            "meta": {
                "message": "User %s updated successfully" % self.userid
            }
        }
        return format_response(200, payload)
