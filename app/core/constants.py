from __future__ import annotations

BASE_IRI_PATH = "/api/v1"


LICENSE_VOCAB: dict[str, dict[str, str]] = {
    "CC0-1.0": {
        "id": "CC0-1.0",
        "label": "Creative Commons Zero v1.0 Universal",
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "spdx": "CC0-1.0",
    },
    "CC-BY-4.0": {
        "id": "CC-BY-4.0",
        "label": "Creative Commons Attribution 4.0 International",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "spdx": "CC-BY-4.0",
    },
    "CC-BY-SA-4.0": {
        "id": "CC-BY-SA-4.0",
        "label": "Creative Commons Attribution-ShareAlike 4.0 International",
        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "spdx": "CC-BY-SA-4.0",
    },
    "CC-BY-NC-4.0": {
        "id": "CC-BY-NC-4.0",
        "label": "Creative Commons Attribution-NonCommercial 4.0 International",
        "url": "https://creativecommons.org/licenses/by-nc/4.0/",
        "spdx": "CC-BY-NC-4.0",
    },
    "MIT": {
        "id": "MIT",
        "label": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
        "spdx": "MIT",
    },
    "Apache-2.0": {
        "id": "Apache-2.0",
        "label": "Apache License 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
        "spdx": "Apache-2.0",
    },
    "ODbL-1.0": {
        "id": "ODbL-1.0",
        "label": "Open Database License v1.0",
        "url": "https://opendatacommons.org/licenses/odbl/1-0/",
        "spdx": "ODbL-1.0",
    },
    "PROPRIETARY": {
        "id": "PROPRIETARY",
        "label": "Proprietary / Restricted",
        "url": "https://fairdatahive.io/vocab#proprietary",
        "spdx": "NOASSERTION",
    },
}


THEME_LIST: list[dict[str, str]] = [
    {"id": "Electrochemistry", "label": "Electrochemistry"},
    {"id": "MaterialsScience", "label": "Materials Science"},
    {"id": "Chemistry", "label": "Chemistry"},
    {"id": "Physics", "label": "Physics"},
    {"id": "Engineering", "label": "Engineering"},
    {"id": "ComputerScience", "label": "Computer Science"},
    {"id": "Biology", "label": "Biology"},
    {"id": "EarthScience", "label": "Earth Science"},
    {"id": "MathematicsAndStatistics", "label": "Mathematics and Statistics"},
    {"id": "Other", "label": "Other"},
]


RESOURCE_STATES = ("draft", "published", "deprecated")

DISTRIBUTION_TYPES = ("upload", "external", "api")

ACCESS_REQUEST_STATUSES = ("pending", "accepted", "rejected", "revoked")

NOTIFICATION_TYPES = (
    "access_requested",
    "access_accepted",
    "access_rejected",
    "access_revoked",
    "resource_published",
    "resource_new_version",
)
