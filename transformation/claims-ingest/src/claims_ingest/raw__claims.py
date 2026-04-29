import json
import random
import requests
import sys
from typing import Any

from pyspark.sql import SparkSession


CLAIMS_URL = "http://localhost:8000/claims"

spark = SparkSession \
    .builder \
    .appName("raw__claims") \
    .getOrCreate()


def get_claims() -> list[dict[str, Any]]:
    """"""
    new_claims_random_gen = max(0, random.gauss(20, 10))
    updates_claims_random_gen = max(0, random.gauss(3, 1))
    duplicates_random_gen = random.choices([True, False], weights=[95, 5], k=1)[0]
    null_patient_id_random_gen = random.choices([True, False], weights=[99, 1], k=1)[0]

    params = {
        "new": new_claims_random_gen,
        "updates": updates_claims_random_gen,
        "duplicates": duplicates_random_gen,
        "null_patient_id": null_patient_id_random_gen
    }

    response = requests.get(
        CLAIMS_URL,
        json.dumps(params)
    )

    response_json = response.json().get("claims", [])

    return response_json

claims_data = get_claims()

if not claims_data:
    print("No claims data")
    sys.exit(0)

df = spark.createDataFrame(claims_data)

