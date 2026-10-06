"""Worker config reads secrets from env; never pass Redis credentials in argv."""

import os
from .redis_broker import QUEUE_NAME

REDIS_URL = os.environ["REDIS_URL"]
QUEUES = [QUEUE_NAME]
SERIALIZER = "rq.serializers.JSONSerializer"
