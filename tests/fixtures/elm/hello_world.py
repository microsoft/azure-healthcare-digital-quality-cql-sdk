"""Integration fixture: a tiny hand-written ELM library used across tests.

Expression: ``Greeting = If 1 + 1 = 2 Then 'Hello, world!' Else 'broken' End``
"""

from __future__ import annotations

HELLO_WORLD_ELM: dict[str, object] = {
    "library": {
        "identifier": {"id": "HelloWorld", "version": "1.0.0"},
        "statements": {
            "def": [
                {
                    "name": "Greeting",
                    "context": "Patient",
                    "accessLevel": "Public",
                    "expression": {
                        "type": "If",
                        "condition": {
                            "type": "Equal",
                            "operand": [
                                {
                                    "type": "Add",
                                    "operand": [
                                        {"type": "Literal", "valueType": "{urn:hl7-org:elm-types:r1}Integer", "value": "1"},
                                        {"type": "Literal", "valueType": "{urn:hl7-org:elm-types:r1}Integer", "value": "1"},
                                    ],
                                },
                                {"type": "Literal", "valueType": "{urn:hl7-org:elm-types:r1}Integer", "value": "2"},
                            ],
                        },
                        "then": {
                            "type": "Literal",
                            "valueType": "{urn:hl7-org:elm-types:r1}String",
                            "value": "Hello, world!",
                        },
                        "else": {
                            "type": "Literal",
                            "valueType": "{urn:hl7-org:elm-types:r1}String",
                            "value": "broken",
                        },
                    },
                },
                {
                    "name": "Sum",
                    "context": "Patient",
                    "accessLevel": "Public",
                    "expression": {
                        "type": "Add",
                        "operand": [
                            {"type": "Literal", "valueType": "{urn:hl7-org:elm-types:r1}Integer", "value": "2"},
                            {"type": "Literal", "valueType": "{urn:hl7-org:elm-types:r1}Integer", "value": "40"},
                        ],
                    },
                },
            ]
        },
    }
}
