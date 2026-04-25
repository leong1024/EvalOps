import os

from evalops.runtime import ApiType

os.environ["LLM_API_TYPE"] = str(ApiType.NONE)
