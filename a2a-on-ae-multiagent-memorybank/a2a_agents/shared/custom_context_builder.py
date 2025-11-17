# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# Author: Gemini

from starlette.requests import Request

from a2a.auth.user import User
from a2a.server.apps.jsonrpc.jsonrpc_app import CallContextBuilder
from a2a.server.context import ServerCallContext


class CustomCallContextBuilder(CallContextBuilder):
    """
    A custom CallContextBuilder that extracts a user_id from the message metadata.
    """

    async def build(self, request: Request) -> ServerCallContext:
        """
        Builds a ServerCallContext by parsing the user_id from the request metadata.
        The frontend sends the user_id in the message.metadata dictionary.
        """
        user_id = "default-user"  # Fallback user_id
        try:
            body = await request.json()
            if (
                "params" in body
                and "message" in body["params"]
                and "metadata" in body["params"]["message"]
                and "user_id" in body["params"]["message"]["metadata"]
            ):
                user_id = body["params"]["message"]["metadata"]["user_id"]

        except Exception:
            # If parsing fails for any reason, we fall back to the default user.
            # In a production system, you might want more robust logging here.
            pass

        # Create a simple User object. For authentication, you'd use a different User class.
        user = User(user_name=user_id, is_authenticated=True)
        
        return ServerCallContext(user=user)
