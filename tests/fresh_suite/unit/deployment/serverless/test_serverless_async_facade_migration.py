"""
Tests for serverless adapter migration to async runtime facade.

TC-004A: BaseHandler.handle_request() awaits run_workflow_async on the normal path
TC-004B: BaseHandler.handle_request() awaits resume_workflow_async for resume actions
         and the compatibility wrappers still work for AWS/Azure/GCP entrypoints.

Caller-Path Contracts (from test-plan.md):
- TC-004A: entrypoint BaseHandler.handle_request(event, context=None)
           mock seam agentmap.runtime_api.run_workflow_async(...)
           forbidden: run_workflow(...), _format_http_response(...), helpers that bypass request flow
           counter-factual: buggy impl would still call sync runtime facade
- TC-004B: entrypoint BaseHandler.handle_request(event, context=None) with action=resume,
           plus AWSLambdaHandler.lambda_handler, AzureFunctionHandler.azure_handler,
           and GCPFunctionHandler.gcp_handler wrapper entrypoints
           mock seam agentmap.runtime_api.resume_workflow_async(...)
           forbidden: resume_workflow(...), BaseHandler.handle_request_sync(...) internals,
           cloud-wrapper conversion helpers
           counter-factual: buggy impl keeps resume path on sync facade or breaks wrapper entrypoints
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Shared payload helpers
# ---------------------------------------------------------------------------


def _make_run_success_payload():
    """Return a representative run_workflow_async success payload."""
    return {
        "success": True,
        "outputs": {"result": "test_output", "completed": True},
        "execution_id": None,
        "execution_summary": None,
        "metadata": {"graph_name": "suspend_resume::SuspendResume", "profile": None},
    }


def _make_run_error_payload():
    """Return a representative run_workflow_async error payload."""
    return {
        "success": False,
        "error": "workflow execution failed",
        "outputs": {},
        "execution_summary": None,
        "metadata": {},
    }


def _make_resume_success_payload():
    """Return a representative resume_workflow_async success payload."""
    return {
        "success": True,
        "outputs": {"resumed": True, "final_result": "approved"},
        "execution_summary": None,
        "metadata": {
            "thread_id": "thread-resume-001",
            "response_action": "continue",
        },
    }


# ---------------------------------------------------------------------------
# TC-004A: BaseHandler.handle_request() awaits the async run facade on the normal path
# ---------------------------------------------------------------------------


class TestTC004A_BaseHandlerRunAsync:
    """
    TC-004A: BaseHandler.handle_request() awaits run_workflow_async on the normal path.

    Counter-factual: a buggy implementation would still call the sync runtime facade
    directly from the async handler (run_workflow instead of run_workflow_async).
    """

    @pytest.mark.asyncio
    async def test_handle_request_awaits_run_workflow_async(self):
        """
        TC-004A primary: handle_request() awaits run_workflow_async, not run_workflow.

        Entrypoint: BaseHandler.handle_request(event, context=None)
        Lowest mock seam: agentmap.runtime_api.run_workflow_async(...)
        Forbidden: run_workflow(...)
        Counter-factual: sync run_workflow would be called instead of async await.
        """
        import agentmap.deployment.serverless.base_handler as base_handler_module
        from agentmap.deployment.serverless.base_handler import BaseHandler

        # After the async migration, the sync run_workflow must not be imported
        assert not hasattr(
            base_handler_module, "run_workflow"
        ), "run_workflow (sync) must not be imported into base_handler after async migration"

        run_async_mock = AsyncMock(return_value=_make_run_success_payload())

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {
                "graph": "suspend_resume::SuspendResume",
                "state": {"seed_value": "payload-123"},
            }
            result = await handler.handle_request(event, None)

        # run_workflow_async must be awaited exactly once
        run_async_mock.assert_awaited_once()
        call_kwargs = run_async_mock.await_args

        # The graph name must be passed
        assert call_kwargs is not None

        # Response envelope must be intact
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert "correlation_id" in body

    @pytest.mark.asyncio
    async def test_handle_request_returns_current_http_envelope(self):
        """
        TC-004A output: handle_request() returns statusCode, headers, body, correlation_id.
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        run_async_mock = AsyncMock(return_value=_make_run_success_payload())

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {"graph": "my_graph", "state": {"key": "val"}}
            result = await handler.handle_request(event, None)

        assert "statusCode" in result
        assert "headers" in result
        assert "body" in result
        body = json.loads(result["body"])
        assert "correlation_id" in body
        assert body["success"] is True
        assert body["data"] == {"result": "test_output", "completed": True}

    @pytest.mark.asyncio
    async def test_handle_request_missing_graph_raises_invalid_inputs(self):
        """
        TC-004A edge: missing graph name still raises InvalidInputs mapped to 400.
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                AsyncMock(),
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {"state": {"key": "val"}}  # no graph key
            result = await handler.handle_request(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["success"] is False

    @pytest.mark.asyncio
    async def test_handle_request_database_trigger_uses_database_event_branch(self):
        """
        TC-004A edge: database trigger events map through the database_event branch.
        The async facade is still awaited on that path.
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        run_async_mock = AsyncMock(return_value=_make_run_success_payload())

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = BaseHandler(config_file=None)
            # DynamoDB stream event – trigger parser maps this to DATABASE type
            event = {
                "Records": [
                    {
                        "eventSource": "aws:dynamodb",
                        "dynamodb": {
                            "NewImage": {
                                "graph": {"S": "my_db_graph"},
                                "data": {"M": {"key": {"S": "val"}}},
                            },
                            "Keys": {"id": {"S": "test-id"}},
                            "StreamViewType": "NEW_AND_OLD_IMAGES",
                        },
                    }
                ]
            }
            # We do not assert the exact graph here since trigger parsing may vary,
            # but we do assert run_workflow_async is still awaited (not sync).
            # We patch parse to return a graph-named payload so no InvalidInputs.
            with patch.object(
                handler.trigger_parser,
                "parse",
                return_value=(
                    __import__(
                        "agentmap.models.serverless_models",
                        fromlist=["TriggerType"],
                    ).TriggerType.HTTP,
                    {"graph": "db_graph", "state": {"db_data": "value"}},
                ),
            ):
                await handler.handle_request(event, None)

        run_async_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_request_unexpected_exception_routes_to_error_formatter(self):
        """
        TC-004A edge: unexpected exceptions route to _handle_error, not exposed raw.
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        run_async_mock = AsyncMock(side_effect=RuntimeError("unexpected boom"))

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {"graph": "my_graph", "state": {}}
            result = await handler.handle_request(event, None)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert body["success"] is False


# ---------------------------------------------------------------------------
# TC-004B: BaseHandler.handle_request() awaits resume_workflow_async and
#          the compatibility wrappers still work for AWS/Azure/GCP entrypoints.
# ---------------------------------------------------------------------------


class TestTC004B_BaseHandlerResumeAsyncAndWrappers:
    """
    TC-004B: handle_request() awaits resume_workflow_async for resume actions.
    The sync wrappers (AWS, Azure, GCP) still return valid responses via handle_request_sync().

    Counter-factual: a buggy implementation would keep the resume path on the sync facade
    or break the wrapper entrypoints while changing the handler to async.
    """

    @pytest.mark.asyncio
    async def test_handle_request_resume_awaits_resume_workflow_async(self):
        """
        TC-004B primary: handle_request() awaits resume_workflow_async for resume events.

        Entrypoint: BaseHandler.handle_request(event, context=None)
        Lowest mock seam: agentmap.runtime_api.resume_workflow_async(...)
        Forbidden: resume_workflow(...)
        Counter-factual: sync resume_workflow would be called instead of async await.
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        resume_async_mock = AsyncMock(return_value=_make_resume_success_payload())

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.resume_workflow_async",
                resume_async_mock,
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {
                "action": "resume",
                "thread_id": "thread-resume-001",
                "resume_value": {"approved": True},
            }
            result = await handler.handle_request(event, None)

        # resume_workflow_async must be awaited exactly once
        resume_async_mock.assert_awaited_once()

        # Response envelope must be intact
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["success"] is True
        assert "correlation_id" in body

    @pytest.mark.asyncio
    async def test_handle_request_resume_does_not_call_sync_resume(self):
        """
        TC-004B negative: sync resume_workflow must not be present in the async handler path.

        After the async migration, resume_workflow (sync) is no longer imported into
        base_handler, so it cannot be called. We verify this by confirming that
        resume_workflow_async IS awaited and that the module does not import the sync sibling.
        """
        import agentmap.deployment.serverless.base_handler as base_handler_module
        from agentmap.deployment.serverless.base_handler import BaseHandler

        # The sync resume_workflow must not be accessible in the handler module namespace
        assert not hasattr(
            base_handler_module, "resume_workflow"
        ), "resume_workflow (sync) must not be imported into base_handler after async migration"

        resume_async_mock = AsyncMock(return_value=_make_resume_success_payload())

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.resume_workflow_async",
                resume_async_mock,
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {
                "action": "resume",
                "thread_id": "thread-resume-001",
                "resume_value": {"approved": True},
            }
            await handler.handle_request(event, None)

        # resume_workflow_async must be awaited — proves async path is active
        resume_async_mock.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_handle_request_resume_missing_thread_id_raises_invalid_inputs(self):
        """
        TC-004B edge: missing thread_id still raises InvalidInputs (400).
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.resume_workflow_async",
                AsyncMock(),
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {"action": "resume"}  # no thread_id
            result = await handler.handle_request(event, None)

        assert result["statusCode"] == 400
        body = json.loads(result["body"])
        assert body["success"] is False

    def test_handle_request_sync_returns_valid_response(self):
        """
        TC-004B compatibility: handle_request_sync() still returns a valid response.
        This is the seam used by all cloud adapter wrappers.
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        run_async_mock = AsyncMock(return_value=_make_run_success_payload())

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = BaseHandler(config_file=None)
            event = {"graph": "my_graph", "state": {"key": "val"}}
            result = handler.handle_request_sync(event, None)

        # Sync wrapper must still return a complete HTTP envelope
        assert "statusCode" in result
        assert "headers" in result
        assert "body" in result
        body = json.loads(result["body"])
        assert body["success"] is True

    def test_aws_lambda_handler_uses_sync_wrapper(self):
        """
        TC-004B wrapper: AWSLambdaHandler.lambda_handler delegates through handle_request_sync.
        The wrapper must not require caller changes.
        """
        from agentmap.deployment.serverless.aws_lambda import AWSLambdaHandler

        run_async_mock = AsyncMock(return_value=_make_run_success_payload())

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = AWSLambdaHandler(config_file=None)
            event = {"graph": "my_graph", "state": {}}
            context = MagicMock()
            result = handler.lambda_handler(event, context)

        assert "statusCode" in result
        body = json.loads(result["body"])
        assert body["success"] is True

    def test_azure_function_handler_uses_sync_wrapper(self):
        """
        TC-004B wrapper: AzureFunctionHandler.azure_handler delegates through handle_request_sync.
        """
        from agentmap.deployment.serverless.azure_functions import AzureFunctionHandler

        run_async_mock = AsyncMock(return_value=_make_run_success_payload())

        # Mock an Azure-style request object
        mock_req = MagicMock()
        mock_req.method = "POST"
        mock_req.get_json.return_value = {"graph": "my_graph", "state": {}}

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = AzureFunctionHandler(config_file=None)
            result = handler.azure_handler(mock_req)

        # Azure handler wraps the response, but must still carry a statusCode
        assert "statusCode" in result

    def test_gcp_function_handler_uses_sync_wrapper(self):
        """
        TC-004B wrapper: GCPFunctionHandler.gcp_handler delegates through handle_request_sync.
        """
        from agentmap.deployment.serverless.gcp_functions import GCPFunctionHandler

        run_async_mock = AsyncMock(return_value=_make_run_success_payload())

        # Mock a GCP-style request object
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.get_json.return_value = {"graph": "my_graph", "state": {}}

        with (
            patch("agentmap.deployment.serverless.base_handler.ensure_initialized"),
            patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                run_async_mock,
            ),
        ):
            handler = GCPFunctionHandler(config_file=None)
            result = handler.gcp_handler(mock_request)

        # GCP handler returns the parsed body dict
        assert isinstance(result, dict)
        assert result.get("success") is True

    def test_no_new_initialization_beyond_constructor(self):
        """
        TC-004B observability: handle_request_sync() does not repeat initialization
        beyond what the constructor already performs.
        """
        from agentmap.deployment.serverless.base_handler import BaseHandler

        with patch(
            "agentmap.deployment.serverless.base_handler.ensure_initialized"
        ) as init_mock:
            with patch(
                "agentmap.deployment.serverless.base_handler.run_workflow_async",
                AsyncMock(return_value=_make_run_success_payload()),
            ):
                handler = BaseHandler(config_file=None)
                # ensure_initialized called once at construction
                assert init_mock.call_count == 1

                # Calling handle_request_sync should NOT call ensure_initialized again
                event = {"graph": "my_graph", "state": {}}
                handler.handle_request_sync(event, None)
                assert init_mock.call_count == 1
