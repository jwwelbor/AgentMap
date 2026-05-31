"""Round-trip serialization tests for GraphBundle.missing_services.

Ensures the field survives serialize -> deserialize and that legacy bundles
(serialized before the field existed) deserialize to an empty set.
"""

import unittest

from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.node import Node
from agentmap.services.graph.bundle_serializer import BundleSerializer
from tests.utils.mock_service_factory import MockServiceFactory


class TestMissingServicesSerialization(unittest.TestCase):
    def setUp(self):
        self.serializer = BundleSerializer(
            MockServiceFactory().create_mock_logging_service()
        )

    def _make_bundle(self, missing_services):
        return GraphBundle.create_metadata(
            graph_name="g",
            nodes={"n1": Node("n1", agent_type="echo")},
            required_agents={"echo"},
            required_services={"logging_service"},
            function_mappings={},
            csv_hash="hash",
            entry_point="n1",
            missing_services=missing_services,
        )

    def test_round_trip_preserves_missing_services(self):
        bundle = self._make_bundle({"bogus_service", "other_service"})

        data = self.serializer.serialize_metadata_bundle(bundle)
        self.assertEqual(data["missing_services"], ["bogus_service", "other_service"])

        restored = self.serializer.deserialize_metadata_bundle(data)
        self.assertEqual(restored.missing_services, {"bogus_service", "other_service"})

    def test_round_trip_empty_missing_services(self):
        bundle = self._make_bundle(set())

        data = self.serializer.serialize_metadata_bundle(bundle)
        restored = self.serializer.deserialize_metadata_bundle(data)

        self.assertEqual(restored.missing_services, set())

    def test_legacy_bundle_without_field_deserializes_to_empty(self):
        bundle = self._make_bundle({"bogus_service"})
        data = self.serializer.serialize_metadata_bundle(bundle)

        # Simulate an old bundle that predates the field.
        del data["missing_services"]

        restored = self.serializer.deserialize_metadata_bundle(data)
        self.assertEqual(restored.missing_services, set())


if __name__ == "__main__":
    unittest.main()
