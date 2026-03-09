import hashlib
import json
from datetime import datetime


class AssetValidator:
    def __init__(self, asset_data):
        self.asset_data = asset_data

    def generate_asset_id(self):
        """
        Generate a unique asset fingerprint
        """
        data_string = json.dumps(self.asset_data, sort_keys=True)
        return hashlib.sha256(data_string.encode()).hexdigest()

    def create_verification_record(self):
        """
        Create verification record
        """
        asset_id = self.generate_asset_id()

        record = {
            "asset_id": asset_id,
            "verified_at": datetime.utcnow().isoformat(),
            "asset_data": self.asset_data
        }

        return record


if __name__ == "__main__":
    example_asset = {
        "owner": "Sample Owner",
        "asset_type": "land",
        "location": "Abuja",
        "size": "500sqm"
    }

    validator = AssetValidator(example_asset)
    record = validator.create_verification_record()

    print(record)